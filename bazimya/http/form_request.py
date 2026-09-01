"""Form requests.

Validation rules and authorisation, moved out of the controller and into a
class of their own under app/Http/Requests.

    class StorePostRequest(FormRequest):
        def authorize(self, request):
            return True

        def rules(self):
            return {
                'title': 'required|max:255',
                'body':  'required',
            }

        def messages(self):
            return {'title.required': 'Give the post a title.'}

Used from a controller:

    def store(self, request):
        data = StorePostRequest.validate(request)
"""

from .exceptions import Forbidden, ValidationException


class FormRequest:
    def authorize(self, request):
        """Return False to answer 403 before validation runs."""
        return True

    def rules(self):
        raise NotImplementedError(
            "{} must implement rules().".format(type(self).__name__)
        )

    def messages(self):
        """Override individual messages, keyed 'field' or 'field.rule'."""
        return {}

    def data(self, request):
        """What gets validated. Override to validate route parameters too."""
        return request.all()

    def prepare(self, request):
        """Runs before validation — normalise input here if you need to."""

    def after(self, validated, request):
        """Runs after validation. Return a replacement for the validated data,
        or None to keep it as it is."""
        return None

    # -- running ----------------------------------------------------------

    @classmethod
    def validate(cls, request):
        """Authorise, validate, and return the validated data.

        Raises Forbidden (403) or ValidationException (422), both of which the
        exception handler already turns into the right response.
        """
        from ..validation import Validator

        instance = cls()

        if not instance.authorize(request):
            raise Forbidden("This action is unauthorised.")

        instance.prepare(request)

        validator = Validator(
            instance.data(request), instance.rules(), instance.messages()
        )

        if validator.fails():
            raise ValidationException(validator.errors)

        validated = validator.validated()
        replacement = instance.after(validated, request)

        return validated if replacement is None else replacement

    @classmethod
    def passes(cls, request):
        """Validate without raising; returns (ok, data_or_errors)."""
        try:
            return True, cls.validate(request)
        except ValidationException as error:
            return False, error.errors
