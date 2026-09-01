"""The base controller.

Its helpers cover what a controller method usually needs to return:

    class PostController(Controller):
        def index(self, request):
            return self.view('posts.index', posts=Post.all())

        def store(self, request):
            post = Post.create(request.only('title', 'body'))

            return self.redirect(self.route('posts.show', id=post.id))
"""

from ..support.aliases import AliasMixin
from .exceptions import abort, abort_if, abort_unless
from .response import Response


class Controller(AliasMixin):
    # -- responses --------------------------------------------------------

    def view(self, template, data=None, status=200, **kwargs):
        from ..facades import View

        payload = dict(data or {})
        payload.update(kwargs)

        return Response.html(View.render(template, payload), status)

    def json(self, data, status=200):
        return Response.json(data, status)

    def text(self, content, status=200):
        return Response.text(content, status)

    def redirect(self, location, status=302):
        return Response.redirect(location, status)

    def redirect_route(self, name, status=302, **parameters):
        return Response.redirect(self.route(name, **parameters), status)

    def back(self, request, fallback="/"):
        return Response.redirect(request.header("referer") or fallback)

    def no_content(self):
        return Response.no_content()

    def download(self, path, name=None):
        return Response.download(path, name)

    # -- helpers ----------------------------------------------------------

    def route(self, name, **parameters):
        from ..facades import Route

        return Route.url(name, **parameters)

    def config(self, key, default=None):
        from ..facades import Config

        return Config.get(key, default)

    def abort(self, status, message=""):
        abort(status, message)

    def abort_if(self, condition, status, message=""):
        abort_if(condition, status, message)

    def abort_unless(self, condition, status, message=""):
        abort_unless(condition, status, message)

    def validate(self, request, rules, messages=None):
        """Validate the request, raising a 422 when it fails.

            data = self.validate(request, {
                'title': 'required|max:255',
                'email': 'required|email',
            })
        """
        from ..validation import Validator

        return Validator(request.all(), rules, messages).validated()
