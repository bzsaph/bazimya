"""Validation.

Laravel's pipe-delimited rule strings, because they are compact and the ones
people already know:

    data = Validator(request.all(), {
        'title': 'required|max:255',
        'email': 'required|email|unique:users,email',
        'age':   'nullable|integer|min:18',
    }).validated()

A failure raises ValidationException, which the exception handler turns into a
422 with the messages attached.
"""

import re

from .http.exceptions import ValidationException

_EMAIL = re.compile(r"^[^@\s]+@[^@\s.]+\.[^@\s]+$")
_URL = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE)
_ALPHA = re.compile(r"^[A-Za-z]+$")
_ALPHA_NUM = re.compile(r"^[A-Za-z0-9]+$")
_ALPHA_DASH = re.compile(r"^[A-Za-z0-9_-]+$")
_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_UUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

DEFAULT_MESSAGES = {
    "required": "The {field} field is required.",
    "email": "The {field} field must be a valid email address.",
    "url": "The {field} field must be a valid URL.",
    "integer": "The {field} field must be a whole number.",
    "numeric": "The {field} field must be a number.",
    "boolean": "The {field} field must be true or false.",
    "alpha": "The {field} field may only contain letters.",
    "alpha_num": "The {field} field may only contain letters and numbers.",
    "alpha_dash": "The {field} field may only contain letters, numbers, dashes and underscores.",
    "slug": "The {field} field must be a valid slug.",
    "uuid": "The {field} field must be a valid UUID.",
    "min": "The {field} field must be at least {parameter}.",
    "max": "The {field} field may not be greater than {parameter}.",
    "between": "The {field} field must be between {parameter}.",
    "size": "The {field} field must be exactly {parameter}.",
    "in": "The selected {field} is invalid.",
    "not_in": "The selected {field} is invalid.",
    "confirmed": "The {field} confirmation does not match.",
    "same": "The {field} and {parameter} fields must match.",
    "different": "The {field} and {parameter} fields must be different.",
    "regex": "The {field} field format is invalid.",
    "date": "The {field} field must be a valid date.",
    "unique": "The {field} has already been taken.",
    "exists": "The selected {field} is invalid.",
    "accepted": "The {field} field must be accepted.",
}


class Validator:
    def __init__(self, data, rules, messages=None):
        self.data = dict(data or {})
        self.rules = dict(rules or {})
        self.messages = dict(messages or {})
        self.errors = {}
        self._validated = {}
        self._ran = False

    # -- running ----------------------------------------------------------

    def passes(self):
        self._run()

        return not self.errors

    def fails(self):
        return not self.passes()

    def validated(self):
        """Return only the validated fields, or raise ValidationException."""
        self._run()

        if self.errors:
            raise ValidationException(self.errors)

        return dict(self._validated)

    def _run(self):
        if self._ran:
            return

        self._ran = True

        for field, rule_string in self.rules.items():
            rules = self._parse(rule_string)
            value = self.data.get(field)

            nullable = any(name == "nullable" for name, _ in rules)
            required = any(name == "required" for name, _ in rules)
            is_empty = value is None or value == ""

            if is_empty:
                if required:
                    self._fail(field, "required", None)
                elif nullable or not required:
                    # Absent and not required: nothing else can be checked,
                    # and running "integer" on None would be a false failure.
                    if field in self.data:
                        self._validated[field] = value

                continue

            failed = False

            for name, parameter in rules:
                if name in ("nullable", "required", "sometimes"):
                    continue

                if name == "__object__":
                    if not parameter.passes(field, value):
                        self.errors.setdefault(field, []).append(parameter.message(field))
                        failed = True
                        break

                    continue

                checker = getattr(self, "_rule_" + name, None)

                if checker is None:
                    raise ValueError(
                        "Unknown validation rule [{}] on field [{}].".format(name, field)
                    )

                if not checker(field, value, parameter):
                    self._fail(field, name, parameter)
                    failed = True
                    break

            if not failed:
                self._validated[field] = value

    @staticmethod
    def _parse(rule_string):
        from .validation_rule import Rule

        if isinstance(rule_string, Rule):
            return [("__object__", rule_string)]

        parts = list(rule_string) if isinstance(rule_string, (list, tuple)) else str(rule_string).split("|")

        parsed = []

        for part in parts:
            # A Rule instance may appear inside a list alongside strings.
            if isinstance(part, Rule):
                parsed.append(("__object__", part))
                continue

            part = str(part).strip()

            if not part:
                continue

            name, _, parameter = part.partition(":")
            parsed.append((name.strip(), parameter.strip() if parameter else None))

        return parsed

    def _fail(self, field, rule, parameter):
        key = "{}.{}".format(field, rule)
        template = self.messages.get(key) or self.messages.get(field) or DEFAULT_MESSAGES.get(
            rule, "The {field} field is invalid."
        )

        message = template.format(
            field=field.replace("_", " "), parameter=parameter, value=self.data.get(field)
        )

        self.errors.setdefault(field, []).append(message)

    # -- rules ------------------------------------------------------------

    def _rule_email(self, field, value, parameter):
        return bool(_EMAIL.match(str(value)))

    def _rule_url(self, field, value, parameter):
        return bool(_URL.match(str(value)))

    def _rule_integer(self, field, value, parameter):
        try:
            int(str(value))

            return True
        except (TypeError, ValueError):
            return False

    def _rule_numeric(self, field, value, parameter):
        try:
            float(str(value))

            return True
        except (TypeError, ValueError):
            return False

    def _rule_boolean(self, field, value, parameter):
        return str(value).lower() in ("1", "0", "true", "false", "yes", "no", "on", "off")

    def _rule_accepted(self, field, value, parameter):
        return str(value).lower() in ("1", "true", "yes", "on")

    def _rule_string(self, field, value, parameter):
        return isinstance(value, str)

    def _rule_alpha(self, field, value, parameter):
        return bool(_ALPHA.match(str(value)))

    def _rule_alpha_num(self, field, value, parameter):
        return bool(_ALPHA_NUM.match(str(value)))

    def _rule_alpha_dash(self, field, value, parameter):
        return bool(_ALPHA_DASH.match(str(value)))

    def _rule_slug(self, field, value, parameter):
        return bool(_SLUG.match(str(value)))

    def _rule_uuid(self, field, value, parameter):
        return bool(_UUID.match(str(value)))

    def _rule_regex(self, field, value, parameter):
        return bool(re.search(parameter or "", str(value)))

    def _rule_min(self, field, value, parameter):
        return self._size(value) >= float(parameter)

    def _rule_max(self, field, value, parameter):
        return self._size(value) <= float(parameter)

    def _rule_size(self, field, value, parameter):
        return self._size(value) == float(parameter)

    def _rule_between(self, field, value, parameter):
        low, _, high = (parameter or "").partition(",")

        return float(low) <= self._size(value) <= float(high)

    def _rule_in(self, field, value, parameter):
        return str(value) in [p.strip() for p in (parameter or "").split(",")]

    def _rule_not_in(self, field, value, parameter):
        return str(value) not in [p.strip() for p in (parameter or "").split(",")]

    def _rule_confirmed(self, field, value, parameter):
        return self.data.get(field + "_confirmation") == value

    def _rule_same(self, field, value, parameter):
        return self.data.get(parameter) == value

    def _rule_different(self, field, value, parameter):
        return self.data.get(parameter) != value

    def _rule_date(self, field, value, parameter):
        from datetime import datetime

        for pattern in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y"):
            try:
                datetime.strptime(str(value), pattern)

                return True
            except ValueError:
                continue

        try:
            datetime.fromisoformat(str(value))

            return True
        except ValueError:
            return False

    def _rule_unique(self, field, value, parameter):
        """unique:table,column[,ignore_id]"""
        table, column, ignore = self._table_rule(parameter, field)

        from .facades import DB

        query = DB.table(table).where(column, value)

        if ignore:
            query = query.where("id", "!=", ignore)

        return not query.exists()

    def _rule_exists(self, field, value, parameter):
        """exists:table,column"""
        table, column, _ = self._table_rule(parameter, field)

        from .facades import DB

        return DB.table(table).where(column, value).exists()

    @staticmethod
    def _table_rule(parameter, field):
        parts = [p.strip() for p in (parameter or "").split(",")]
        table = parts[0] if parts and parts[0] else None

        if not table:
            raise ValueError(
                "The unique/exists rule on [{}] needs a table: 'unique:users,email'".format(field)
            )

        column = parts[1] if len(parts) > 1 and parts[1] else field
        ignore = parts[2] if len(parts) > 2 and parts[2] else None

        return table, column, ignore

    @staticmethod
    def _size(value):
        """Numbers compare by value; everything else by length — the same
        rule Laravel uses, and the reason min:18 works on an age and min:8 on
        a password."""
        if isinstance(value, bool):
            return 1

        if isinstance(value, (int, float)):
            return float(value)

        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return float(len(value))

        try:
            return float(len(value))
        except TypeError:
            return 0.0


def validate(data, rules, messages=None):
    """One-shot helper: returns the validated data or raises."""
    return Validator(data, rules, messages).validated()
