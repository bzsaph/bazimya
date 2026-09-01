"""Custom validation rules — Laravel's app/Rules.

    class Uppercase(Rule):
        def passes(self, field, value):
            return str(value) == str(value).upper()

        def message(self, field):
            return "The {} field must be uppercase.".format(field)

Use it by passing the instance instead of a rule string:

    Validator(request.all(), {'code': Uppercase()})
"""


class Rule:
    def passes(self, field, value):
        raise NotImplementedError(
            "{} must implement passes(self, field, value).".format(type(self).__name__)
        )

    def message(self, field):
        return "The {} field is invalid.".format(field.replace("_", " "))
