"""The query builder.

Chained, so a query reads in the order it runs:

    DB.table('users').where('active', 1).order_by('name').limit(10).get()
    DB.table('users').where('age', '>=', 18).count()
    DB.table('users').insert({'name': 'James', 'email': 'j@example.com'})

Every value goes through a bound parameter. Identifiers (table and column
names) cannot be bound by the driver, so they are validated instead — a column
name is never interpolated unless it looks like one.
"""

import re

from ..support.aliases import AliasMixin
from .connection import QueryError

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?$")

OPERATORS = {
    "=", "<", ">", "<=", ">=", "<>", "!=",
    "like", "not like", "ilike", "in", "not in", "is", "is not",
}


def _identifier(name, what="column"):
    """Reject anything that is not a bare identifier.

    Bindings protect values; nothing protects identifiers, so a column name
    arriving from request data is the obvious way a builder gets exploited.
    """
    if name == "*":
        return name

    if not isinstance(name, str) or not _IDENTIFIER.match(name):
        raise QueryError(
            "{!r} is not a valid {} name. Column and table names must be plain "
            "identifiers — they cannot be bound as parameters, so they are never "
            "interpolated from untrusted input.".format(name, what)
        )

    return name


class QueryBuilder(AliasMixin):
    def __init__(self, connection, table):
        self.connection = connection
        self.table_name = _identifier(table, "table")

        self._columns = ["*"]
        self._wheres = []
        self._bindings = []
        self._orders = []
        self._groups = []
        self._havings = []
        self._joins = []
        self._limit = None
        self._offset = None
        self._distinct = False

    # -- selecting --------------------------------------------------------

    def select(self, *columns):
        flat = []

        for column in columns:
            flat.extend(column if isinstance(column, (list, tuple)) else [column])

        self._columns = [_identifier(c) for c in flat] or ["*"]

        return self

    def distinct(self):
        self._distinct = True

        return self

    # -- filtering --------------------------------------------------------

    def where(self, column, operator=None, value=None, boolean="AND"):
        """where('id', 3) or where('age', '>=', 18)."""
        if callable(column):
            return self._where_nested(column, boolean)

        if isinstance(column, dict):
            for key, item in column.items():
                self.where(key, "=", item, boolean)

            return self

        # Two arguments means the operator was left out.
        if value is None and operator is not None and str(operator).lower() not in OPERATORS:
            value, operator = operator, "="

        operator = str(operator or "=").lower()

        if operator not in OPERATORS:
            raise QueryError("Unsupported operator [{}].".format(operator))

        column = _identifier(column)

        if value is None and operator in ("=", "is"):
            self._wheres.append((boolean, "{} IS NULL".format(self.connection.wrap(column))))

            return self

        if value is None and operator in ("!=", "<>", "is not"):
            self._wheres.append((boolean, "{} IS NOT NULL".format(self.connection.wrap(column))))

            return self

        self._wheres.append(
            (boolean, "{} {} ?".format(self.connection.wrap(column), operator.upper()))
        )
        self._bindings.append(value)

        return self

    def or_where(self, column, operator=None, value=None):
        return self.where(column, operator, value, boolean="OR")

    def _where_nested(self, callback, boolean):
        """where(lambda q: q.where(...).or_where(...)) — a parenthesised group."""
        nested = QueryBuilder(self.connection, self.table_name)
        callback(nested)

        if not nested._wheres:
            return self

        clause, bindings = nested._compile_wheres(bare=True)
        self._wheres.append((boolean, "({})".format(clause)))
        self._bindings.extend(bindings)

        return self

    def where_in(self, column, values, boolean="AND", negate=False):
        column = _identifier(column)
        values = list(values)

        if not values:
            # IN () is a syntax error; an empty set matches nothing (or, when
            # negated, everything).
            self._wheres.append((boolean, "1 = 0" if not negate else "1 = 1"))

            return self

        placeholders = ", ".join("?" for _ in values)
        self._wheres.append(
            (
                boolean,
                "{} {}IN ({})".format(
                    self.connection.wrap(column), "NOT " if negate else "", placeholders
                ),
            )
        )
        self._bindings.extend(values)

        return self

    def where_not_in(self, column, values):
        return self.where_in(column, values, negate=True)

    def or_where_in(self, column, values):
        return self.where_in(column, values, boolean="OR")

    def where_null(self, column, boolean="AND", negate=False):
        column = _identifier(column)
        self._wheres.append(
            (boolean, "{} IS {}NULL".format(self.connection.wrap(column), "NOT " if negate else ""))
        )

        return self

    def where_not_null(self, column):
        return self.where_null(column, negate=True)

    def where_between(self, column, low, high, boolean="AND"):
        column = _identifier(column)
        self._wheres.append((boolean, "{} BETWEEN ? AND ?".format(self.connection.wrap(column))))
        self._bindings.extend([low, high])

        return self

    def where_like(self, column, pattern):
        return self.where(column, "like", pattern)

    def where_raw(self, sql, bindings=None):
        """An escape hatch. You are responsible for what goes in `sql` —
        pass values through `bindings`, never by formatting them in."""
        self._wheres.append(("AND", "({})".format(sql)))
        self._bindings.extend(list(bindings or []))

        return self

    # -- joins ------------------------------------------------------------

    def join(self, table, first, operator, second, kind="INNER"):
        table = _identifier(table, "table")

        self._joins.append(
            "{} JOIN {} ON {} {} {}".format(
                kind,
                self.connection.wrap(table),
                self.connection.wrap(_identifier(first)),
                operator if operator in ("=", "<", ">", "<=", ">=", "!=", "<>") else "=",
                self.connection.wrap(_identifier(second)),
            )
        )

        return self

    def left_join(self, table, first, operator, second):
        return self.join(table, first, operator, second, kind="LEFT")

    def right_join(self, table, first, operator, second):
        return self.join(table, first, operator, second, kind="RIGHT")

    # -- ordering, grouping, paging ---------------------------------------

    def order_by(self, column, direction="asc"):
        direction = "DESC" if str(direction).lower() in ("desc", "descending") else "ASC"
        self._orders.append("{} {}".format(self.connection.wrap(_identifier(column)), direction))

        return self

    def order_by_desc(self, column):
        return self.order_by(column, "desc")

    def latest(self, column="created_at"):
        return self.order_by(column, "desc")

    def oldest(self, column="created_at"):
        return self.order_by(column, "asc")

    def group_by(self, *columns):
        for column in columns:
            self._groups.append(self.connection.wrap(_identifier(column)))

        return self

    def having(self, column, operator, value):
        self._havings.append(
            ("AND", "{} {} ?".format(self.connection.wrap(_identifier(column)), operator))
        )
        self._bindings.append(value)

        return self

    def limit(self, count):
        self._limit = max(0, int(count))

        return self

    def offset(self, count):
        self._offset = max(0, int(count))

        return self

    def take(self, count):
        return self.limit(count)

    def skip(self, count):
        return self.offset(count)

    def for_page(self, page, per_page=15):
        page = max(1, int(page))

        return self.offset((page - 1) * per_page).limit(per_page)

    # -- compiling --------------------------------------------------------

    def _compile_wheres(self, bare=False):
        if not self._wheres:
            return "", []

        clause = ""

        for index, (boolean, condition) in enumerate(self._wheres):
            clause += condition if index == 0 else " {} {}".format(boolean, condition)

        return (clause if bare else " WHERE " + clause), list(self._bindings)

    def to_sql(self):
        columns = ", ".join(self.connection.wrap(c) for c in self._columns)

        sql = "SELECT {}{} FROM {}".format(
            "DISTINCT " if self._distinct else "",
            columns,
            self.connection.wrap(self.table_name),
        )

        for join in self._joins:
            sql += " " + join

        where, _ = self._compile_wheres()
        sql += where

        if self._groups:
            sql += " GROUP BY " + ", ".join(self._groups)

        if self._havings:
            sql += " HAVING " + " AND ".join(condition for _, condition in self._havings)

        if self._orders:
            sql += " ORDER BY " + ", ".join(self._orders)

        if self._limit is not None:
            sql += " LIMIT {}".format(self._limit)

        if self._offset is not None:
            # SQLite and MySQL both need a LIMIT before OFFSET.
            if self._limit is None:
                sql += " LIMIT -1" if self.connection.driver == "sqlite" else " LIMIT 18446744073709551615"

            sql += " OFFSET {}".format(self._offset)

        return sql

    def bindings(self):
        return list(self._bindings)

    # -- reading ----------------------------------------------------------

    def get(self):
        return self.connection.select(self.to_sql(), self._bindings)

    def first(self):
        rows = self.limit(1).get()

        return rows[0] if rows else None

    def find(self, identifier, column="id"):
        return self.where(column, identifier).first()

    def value(self, column):
        row = self.select(column).first()

        return row.get(column) if row else None

    def pluck(self, column, key=None):
        columns = [column] if key is None else [key, column]
        rows = self.select(*columns).get()

        if key is None:
            return [row.get(column) for row in rows]

        return {row.get(key): row.get(column) for row in rows}

    def exists(self):
        return self.count() > 0

    def count(self, column="*"):
        return int(self._aggregate("COUNT", column) or 0)

    def sum(self, column):
        return self._aggregate("SUM", column) or 0

    def avg(self, column):
        return self._aggregate("AVG", column)

    def max(self, column):
        return self._aggregate("MAX", column)

    def min(self, column):
        return self._aggregate("MIN", column)

    def _aggregate(self, function, column):
        expression = "*" if column == "*" else self.connection.wrap(_identifier(column))

        sql = "SELECT {}({}) AS aggregate FROM {}".format(
            function, expression, self.connection.wrap(self.table_name)
        )

        for join in self._joins:
            sql += " " + join

        where, bindings = self._compile_wheres()
        sql += where

        row = self.connection.select_one(sql, bindings)

        return row.get("aggregate") if row else None

    def chunk(self, size, callback):
        """Walk a large table without loading all of it."""
        page = 1

        while True:
            rows = self.for_page(page, size).get()

            if not rows:
                return True

            if callback(rows, page) is False:
                return False

            if len(rows) < size:
                return True

            page += 1

    def paginate(self, page=1, per_page=15):
        total = self.count()
        rows = self.for_page(page, per_page).get()
        last = max(1, -(-total // per_page))

        return {
            "data": rows,
            "total": total,
            "per_page": per_page,
            "current_page": page,
            "last_page": last,
            "from": (page - 1) * per_page + 1 if rows else None,
            "to": (page - 1) * per_page + len(rows) if rows else None,
        }

    # -- writing ----------------------------------------------------------

    def insert(self, values):
        """Insert one dict, or a list of dicts. Returns the last inserted id."""
        if isinstance(values, (list, tuple)):
            last = None

            for row in values:
                last = self.insert(row)

            return last

        if not values:
            raise QueryError("insert() was given nothing to insert.")

        columns = [_identifier(c) for c in values]
        placeholders = ", ".join("?" for _ in columns)

        sql = "INSERT INTO {} ({}) VALUES ({})".format(
            self.connection.wrap(self.table_name),
            ", ".join(self.connection.wrap(c) for c in columns),
            placeholders,
        )

        return self.connection.insert(sql, [values[c] for c in columns])

    def update(self, values):
        if not values:
            return 0

        columns = [_identifier(c) for c in values]
        assignments = ", ".join("{} = ?".format(self.connection.wrap(c)) for c in columns)

        sql = "UPDATE {} SET {}".format(self.connection.wrap(self.table_name), assignments)
        bindings = [values[c] for c in columns]

        where, where_bindings = self._compile_wheres()
        sql += where
        bindings.extend(where_bindings)

        return self.connection.update(sql, bindings)

    def increment(self, column, amount=1):
        column = _identifier(column)
        wrapped = self.connection.wrap(column)

        sql = "UPDATE {} SET {} = {} + ?".format(
            self.connection.wrap(self.table_name), wrapped, wrapped
        )
        bindings = [amount]

        where, where_bindings = self._compile_wheres()
        sql += where
        bindings.extend(where_bindings)

        return self.connection.update(sql, bindings)

    def decrement(self, column, amount=1):
        return self.increment(column, -amount)

    def delete(self):
        sql = "DELETE FROM {}".format(self.connection.wrap(self.table_name))

        where, bindings = self._compile_wheres()

        if not where:
            raise QueryError(
                "delete() without a where clause would empty {}. Call truncate() "
                "if that is what you mean.".format(self.table_name)
            )

        return self.connection.delete(sql + where, bindings)

    def truncate(self):
        return self.connection.statement(
            "DELETE FROM {}".format(self.connection.wrap(self.table_name))
        )

    def __repr__(self):
        return "<QueryBuilder {}>".format(self.to_sql())
