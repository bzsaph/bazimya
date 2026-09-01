"""Authentication.

The Auth facade over a session guard:

    if Auth.attempt({'email': email, 'password': password}):
        request.session().regenerate()

        return redirect('/dashboard')

    Auth.user()      the logged-in model, or None
    Auth.check()     True when someone is logged in
    Auth.logout()

The guard reads its user model from config/auth.py, so it works with whatever
model you point it at rather than assuming `User`.
"""


class AuthenticationError(RuntimeError):
    pass


class SessionGuard:
    """Keeps the authenticated user's id in the session."""

    SESSION_KEY = "_auth_id"
    PASSWORD_HASH_KEY = "_auth_password"

    def __init__(self, application, config=None):
        self.app = application
        self.config = dict(config or {})
        self._user = None
        self._resolved = False
        self._session = None

    # -- wiring -----------------------------------------------------------

    def set_session(self, session):
        """Called by StartSession, once per request."""
        self._session = session
        self._user = None
        self._resolved = False

        return self

    def session(self):
        return self._session

    def provider_model(self):
        """The model this guard authenticates, named in config/auth.py."""
        reference = self.config.get("model", "app.Models.User.User")

        if not isinstance(reference, str):
            return reference

        import importlib

        module_name, _, class_name = reference.rpartition(".")

        try:
            module = importlib.import_module(module_name)
        except ImportError as error:
            raise AuthenticationError(
                "The auth model [{}] could not be imported. Check "
                "auth.providers.users.model in config/auth.py.".format(reference)
            ) from error

        model = getattr(module, class_name, None)

        if model is None:
            raise AuthenticationError(
                "The auth model [{}] was not found.".format(reference)
            )

        return model

    def hasher(self):
        return self.app.make("hash")

    # -- reading the current user -----------------------------------------

    def user(self):
        if self._resolved:
            return self._user

        self._resolved = True

        if self._session is None:
            return None

        identifier = self._session.get(self.SESSION_KEY)

        if identifier is None:
            return None

        model = self.provider_model()
        user = model.find(identifier)

        # A password change should end other sessions. The stored fragment is
        # compared, so an old cookie stops working once the hash changes.
        if user is not None and not self._password_still_valid(user):
            self._session.forget(self.SESSION_KEY, self.PASSWORD_HASH_KEY)

            return None

        self._user = user

        return user

    def _password_still_valid(self, user):
        remembered = self._session.get(self.PASSWORD_HASH_KEY)

        if remembered is None:
            return True

        return remembered == self._password_fingerprint(user)

    @staticmethod
    def _password_fingerprint(user):
        import hashlib

        password = user.attributes().get("password") or ""

        return hashlib.sha256(str(password).encode("utf-8")).hexdigest()[:32]

    def id(self):
        user = self.user()

        return user.key() if user is not None else None

    def check(self):
        return self.user() is not None

    def guest(self):
        return not self.check()

    # -- logging in and out -----------------------------------------------

    def attempt(self, credentials, remember=False):
        """Find a matching user and verify the password.

        Returns True on success. The password is verified even when no user
        matched, so that a wrong email and a wrong password take the same time
        and the response cannot be used to enumerate accounts.
        """
        credentials = dict(credentials or {})
        password = credentials.pop("password", None)

        user = self.retrieve_by_credentials(credentials)

        if user is None:
            self.hasher().check(str(password or ""), _DUMMY_HASH)

            return False

        if not self.validate_password(user, password):
            return False

        self.login(user, remember)

        return True

    def retrieve_by_credentials(self, credentials):
        if not credentials:
            return None

        model = self.provider_model()
        query = model.query()

        for column, value in credentials.items():
            query = query.where(column, value)

        return query.first()

    def validate_password(self, user, password):
        stored = user.attributes().get("password")

        if not stored:
            return False

        if not self.hasher().check(str(password or ""), stored):
            return False

        # Upgrade the stored hash when the configured cost has moved on. This
        # is the only moment the plaintext is available to do it.
        if self.hasher().needs_rehash(stored):
            user.force_fill({"password": self.hasher().make(password)})
            user.save()

        return True

    def login(self, user, remember=False):
        if self._session is None:
            raise AuthenticationError(
                "There is no session to log in to. Add StartSession to the "
                "middleware group for this route."
            )

        # A new session id on login is what closes off session fixation: any
        # id an attacker planted before login stops being the one in use.
        self._session.regenerate()
        self._session.put(self.SESSION_KEY, user.key())
        self._session.put(self.PASSWORD_HASH_KEY, self._password_fingerprint(user))

        self._user = user
        self._resolved = True

        return user

    def login_using_id(self, identifier):
        user = self.provider_model().find(identifier)

        return self.login(user) if user is not None else None

    def once(self, credentials):
        """Verify credentials without touching the session."""
        user = self.retrieve_by_credentials(
            {k: v for k, v in credentials.items() if k != "password"}
        )

        if user is None or not self.validate_password(user, credentials.get("password")):
            return False

        self._user = user
        self._resolved = True

        return True

    def logout(self):
        if self._session is not None:
            self._session.forget(self.SESSION_KEY, self.PASSWORD_HASH_KEY)
            self._session.invalidate()

        self._user = None
        self._resolved = True

        return self

    def set_user(self, user):
        self._user = user
        self._resolved = True

        return self


#: A real hash of a random value, so a failed lookup still costs one
#: verification and the timing of "no such user" matches "wrong password".
_DUMMY_HASH = (
    "pbkdf2$480000$AAAAAAAAAAAAAAAAAAAAAA$"
    "cGxhY2Vob2xkZXJwbGFjZWhvbGRlcnBsYWNlaG9sZGVy"
)
