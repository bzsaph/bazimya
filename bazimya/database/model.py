"""Models.

Eloquent's shape, in Python:

    class User(Model):
        table = 'users'
        fillable = ['name', 'email']
        hidden = ['password']
        casts = {'active': bool}

    user = User.create({'name': 'James', 'email': 'j@example.com'})
    user = User.find(1)
    user.name = 'James M.'
    user.save()

    User.where('active', 1).order_by('name').get()

Attributes are read and written as normal Python attributes; the underlying
row is a dict, and `to_dict()` gives it back with hidden fields removed.
"""

from datetime import datetime

from ..support.aliases import AliasMeta, AliasMixin, camel_to_snake, looks_camel
from .query import QueryBuilder

_INTERNAL = {"_attributes", "_original", "_exists"}


class ModelQuery:
    """A QueryBuilder whose results come back as model instances."""

    def __init__(self, model_class, builder):
        self._model = model_class
        self._builder = builder

    # Anything not defined here is a builder method; keep the chain going by
    # returning self when the builder returns itself.
    def __getattr__(self, name):
        # firstOrFail lives here, not on the builder, so camelCase has to be
        # resolved against this object before anything is delegated.
        if looks_camel(name):
            snake = camel_to_snake(name)

            if snake != name:
                try:
                    return object.__getattribute__(self, snake)
                except AttributeError:
                    pass

        attribute = getattr(self._builder, name)

        if not callable(attribute):
            return attribute

        def wrapper(*args, **kwargs):
            result = attribute(*args, **kwargs)

            return self if result is self._builder else result

        return wrapper

    def get(self):
        return [self._model.hydrate(row) for row in self._builder.get()]

    def first(self):
        row = self._builder.first()

        return self._model.hydrate(row) if row else None

    def first_or_fail(self):
        instance = self.first()

        if instance is None:
            raise ModelNotFound(
                "No {} matched the query.".format(self._model.__name__)
            )

        return instance

    def find(self, identifier):
        row = self._builder.where(self._model.primary_key, identifier).first()

        return self._model.hydrate(row) if row else None

    def paginate(self, page=1, per_page=15):
        result = self._builder.paginate(page, per_page)
        result["data"] = [self._model.hydrate(row) for row in result["data"]]

        return result

    def chunk(self, size, callback):
        return self._builder.chunk(
            size, lambda rows, page: callback([self._model.hydrate(r) for r in rows], page)
        )

    def __iter__(self):
        return iter(self.get())

    def __repr__(self):
        return "<ModelQuery {}>".format(self._builder.to_sql())


class ModelNotFound(LookupError):
    pass


class Model(AliasMixin, metaclass=AliasMeta):
    #: Override when the pluralised class name is not the table name.
    table = None

    primary_key = "id"

    #: Only these may be mass-assigned. Empty means "nothing", deliberately:
    #: an empty fillable list should not silently allow everything.
    fillable = []

    #: Never mass-assignable, even if listed in fillable.
    guarded = ["id"]

    #: Left out of to_dict() and JSON responses.
    hidden = []

    #: {'active': bool, 'meta': 'json'} — applied when reading.
    casts = {}

    #: Maintain created_at / updated_at automatically.
    timestamps = True

    created_at = "created_at"
    updated_at = "updated_at"

    def __init__(self, attributes=None, exists=False):
        object.__setattr__(self, "_attributes", dict(attributes or {}))
        object.__setattr__(self, "_original", dict(attributes or {}))
        object.__setattr__(self, "_exists", exists)

    # -- naming -----------------------------------------------------------

    @classmethod
    def table_name(cls):
        if cls.table:
            return cls.table

        from ..support.strings import plural, snake

        return plural(snake(cls.__name__))

    @classmethod
    def connection(cls):
        from ..facades import DB

        return DB.connection()

    @classmethod
    def query(cls):
        return ModelQuery(cls, QueryBuilder(cls.connection(), cls.table_name()))

    # -- reading ----------------------------------------------------------

    @classmethod
    def hydrate(cls, row):
        instance = cls(row, exists=True)

        return instance

    @classmethod
    def all(cls):
        return cls.query().get()

    @classmethod
    def find(cls, identifier):
        return cls.query().find(identifier)

    @classmethod
    def find_or_fail(cls, identifier):
        instance = cls.find(identifier)

        if instance is None:
            raise ModelNotFound(
                "{} [{}] was not found.".format(cls.__name__, identifier)
            )

        return instance

    @classmethod
    def where(cls, *args, **kwargs):
        return cls.query().where(*args, **kwargs)

    @classmethod
    def where_in(cls, column, values):
        return cls.query().where_in(column, values)

    @classmethod
    def order_by(cls, column, direction="asc"):
        return cls.query().order_by(column, direction)

    @classmethod
    def latest(cls, column=None):
        return cls.query().order_by(column or cls.created_at, "desc")

    @classmethod
    def limit(cls, count):
        return cls.query().limit(count)

    @classmethod
    def paginate(cls, page=1, per_page=15):
        return cls.query().paginate(page, per_page)

    @classmethod
    def count(cls):
        return cls.query().count()

    @classmethod
    def first(cls):
        return cls.query().first()

    @classmethod
    def exists(cls, identifier):
        return cls.query().where(cls.primary_key, identifier).exists()

    # -- writing ----------------------------------------------------------

    @classmethod
    def create(cls, attributes=None, **kwargs):
        values = dict(attributes or {})
        values.update(kwargs)

        instance = cls(cls.filter_fillable(values))
        instance.save()

        return instance

    @classmethod
    def first_or_create(cls, match, defaults=None):
        query = cls.query()

        for column, value in match.items():
            query = query.where(column, value)

        existing = query.first()

        if existing is not None:
            return existing

        values = dict(match)
        values.update(defaults or {})

        return cls.create(values)

    @classmethod
    def update_or_create(cls, match, values=None):
        query = cls.query()

        for column, value in match.items():
            query = query.where(column, value)

        existing = query.first()

        if existing is None:
            merged = dict(match)
            merged.update(values or {})

            return cls.create(merged)

        existing.fill(values or {})
        existing.save()

        return existing

    @classmethod
    def destroy(cls, *identifiers):
        flat = []

        for identifier in identifiers:
            flat.extend(identifier if isinstance(identifier, (list, tuple)) else [identifier])

        if not flat:
            return 0

        return (
            QueryBuilder(cls.connection(), cls.table_name())
            .where_in(cls.primary_key, flat)
            .delete()
        )

    @classmethod
    def filter_fillable(cls, values):
        """Mass assignment obeys fillable/guarded, so a stray field in a form
        post cannot set a column the model never meant to expose."""
        guarded = set(cls.guarded)

        if cls.fillable:
            return {k: v for k, v in values.items() if k in cls.fillable and k not in guarded}

        return {k: v for k, v in values.items() if k not in guarded}

    def fill(self, values):
        self._attributes.update(self.filter_fillable(values))

        return self

    def force_fill(self, values):
        """Bypass fillable — for trusted, internal writes only."""
        self._attributes.update(values)

        return self

    def save(self):
        builder = QueryBuilder(self.connection(), self.table_name())
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if self._exists:
            changes = self.dirty()

            if not changes:
                return self

            if self.timestamps:
                changes[self.updated_at] = now
                self._attributes[self.updated_at] = now

            builder.where(self.primary_key, self.key()).update(changes)
        else:
            values = dict(self._attributes)

            if self.timestamps:
                values.setdefault(self.created_at, now)
                values.setdefault(self.updated_at, now)

            identifier = builder.insert(values)

            self._attributes.update(values)

            if self.primary_key not in self._attributes and identifier is not None:
                self._attributes[self.primary_key] = identifier

            object.__setattr__(self, "_exists", True)

        object.__setattr__(self, "_original", dict(self._attributes))

        return self

    def update(self, values=None, **kwargs):
        merged = dict(values or {})
        merged.update(kwargs)

        self.fill(merged)

        return self.save()

    def delete(self):
        if not self._exists:
            return False

        deleted = (
            QueryBuilder(self.connection(), self.table_name())
            .where(self.primary_key, self.key())
            .delete()
        )

        object.__setattr__(self, "_exists", False)

        return bool(deleted)

    def refresh(self):
        fresh = type(self).find(self.key())

        if fresh is not None:
            object.__setattr__(self, "_attributes", dict(fresh._attributes))
            object.__setattr__(self, "_original", dict(fresh._attributes))

        return self

    # -- state ------------------------------------------------------------

    def key(self):
        return self._attributes.get(self.primary_key)

    def dirty(self):
        return {
            key: value
            for key, value in self._attributes.items()
            if key not in self._original or self._original[key] != value
        }

    def is_dirty(self):
        return bool(self.dirty())

    def exists_in_database(self):
        return self._exists

    # -- attribute access -------------------------------------------------

    def __getattr__(self, name):
        # Only reached when normal lookup fails, so class attributes and
        # methods still win over columns of the same name.
        attributes = object.__getattribute__(self, "_attributes")

        if name in attributes:
            return type(self)._cast(name, attributes[name])

        if looks_camel(name):
            snake = camel_to_snake(name)

            if snake in attributes:
                return type(self)._cast(snake, attributes[snake])

            if snake != name:
                try:
                    return object.__getattribute__(self, snake)
                except AttributeError:
                    pass

        raise AttributeError(
            "{} has no attribute or column [{}].".format(type(self).__name__, name)
        )

    def __setattr__(self, name, value):
        if name in _INTERNAL or name.startswith("__"):
            object.__setattr__(self, name, value)

            return

        # A real class attribute (a method, a config field) is set normally;
        # anything else is a column.
        if hasattr(type(self), name) and not isinstance(
            getattr(type(self), name, None), (str, int, float, bool, list, dict, type(None))
        ):
            object.__setattr__(self, name, value)

            return

        self._attributes[name] = value

    def __getitem__(self, key):
        return type(self)._cast(key, self._attributes[key])

    def __setitem__(self, key, value):
        self._attributes[key] = value

    def __contains__(self, key):
        return key in self._attributes

    @classmethod
    def _cast(cls, name, value):
        cast = cls.casts.get(name)

        if cast is None or value is None:
            return value

        try:
            if cast is bool or cast == "bool":
                return bool(value) if not isinstance(value, str) else value.lower() in ("1", "true", "yes", "on")

            if cast is int or cast == "int":
                return int(value)

            if cast is float or cast == "float":
                return float(value)

            if cast == "json":
                import json

                return json.loads(value) if isinstance(value, str) else value

            if cast == "datetime":
                return (
                    datetime.fromisoformat(value) if isinstance(value, str) else value
                )

            if callable(cast):
                return cast(value)
        except (TypeError, ValueError):
            # A cast that cannot be applied should not break the read; the raw
            # value is more useful than an exception halfway through a page.
            return value

        return value

    # -- serialisation ----------------------------------------------------

    def to_dict(self):
        hidden = set(self.hidden)

        return {
            key: type(self)._cast(key, value)
            for key, value in self._attributes.items()
            if key not in hidden
        }

    def attributes(self):
        """Every attribute, hidden ones included. For internal use."""
        return dict(self._attributes)

    def to_json(self):
        import json

        return json.dumps(self.to_dict(), default=str)

    def __repr__(self):
        return "<{} {}={}>".format(type(self).__name__, self.primary_key, self.key())

    def __eq__(self, other):
        return (
            isinstance(other, type(self))
            and self.key() is not None
            and self.key() == other.key()
        )

    def __hash__(self):
        return hash((type(self).__name__, self.key()))
