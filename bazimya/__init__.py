"""Bazimya — a Python web framework with Laravel's structure.

Everything an application needs is importable from here:

    from bazimya import Route, Controller, Model, Schema, Migration, Response

The layout, the vocabulary and the lifecycle follow Laravel 10; the language
is Python, and templates are .baz.html.
"""

from .database.migration import Migration, Migrator
from .database.model import Model, ModelNotFound
from .database.query import QueryBuilder
from .database.schema import Blueprint, Schema
from .console.command import Command
from .console.registry import Console
from .extensions.extension import Extension
from .facades import (
    App,
    Auth,
    Cache,
    Config,
    DB,
    Event,
    Extensions,
    Hash,
    Mail,
    Notify,
    Route,
    Session,
    Storage,
    View,
    app,
    auth,
    back,
    csrf_token,
    old,
    base_path,
    config,
    database_path,
    public_path,
    redirect,
    resource_path,
    route,
    storage_path,
    view,
)
from .foundation.application import VERSION, Application
from .foundation.container import Container
from .foundation.provider import ServiceProvider
from .http.controller import Controller
from .http.form_request import FormRequest
from .http.exceptions import (
    BadRequest,
    Forbidden,
    HttpException,
    NotFound,
    Unauthorized,
    ValidationException,
    abort,
    abort_if,
    abort_unless,
)
from .auth.middleware import Authenticate, RedirectIfAuthenticated
from .http.middleware import Middleware
from .notifications.notification import Notification
from .session.middleware import ShareErrorsFromSession, StartSession, VerifyCsrfToken
from .view.components import Component
from .http.request import Request
from .http.response import Response
from .support.env import Env, env
from .validation import Validator, validate
from .validation_rule import Rule
from .view.view import markup

__version__ = VERSION

__all__ = [
    "App",
    "Application",
    "Auth",
    "Authenticate",
    "BadRequest",
    "Cache",
    "Blueprint",
    "Command",
    "Component",
    "Config",
    "Console",
    "Container",
    "Controller",
    "DB",
    "Env",
    "Event",
    "Extension",
    "Extensions",
    "Forbidden",
    "Hash",
    "FormRequest",
    "HttpException",
    "Middleware",
    "Migration",
    "Migrator",
    "Model",
    "ModelNotFound",
    "NotFound",
    "Notification",
    "Notify",
    "QueryBuilder",
    "Request",
    "RedirectIfAuthenticated",
    "Response",
    "Route",
    "Rule",
    "Schema",
    "Session",
    "ServiceProvider",
    "ShareErrorsFromSession",
    "StartSession",
    "Storage",
    "Unauthorized",
    "ValidationException",
    "VerifyCsrfToken",
    "Validator",
    "View",
    "abort",
    "abort_if",
    "abort_unless",
    "app",
    "auth",
    "back",
    "base_path",
    "config",
    "csrf_token",
    "database_path",
    "env",
    "markup",
    "old",
    "public_path",
    "redirect",
    "resource_path",
    "route",
    "storage_path",
    "validate",
    "view",
]
