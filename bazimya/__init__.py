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
    Config,
    DB,
    Extensions,
    Route,
    View,
    app,
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
from .http.middleware import Middleware
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
    "BadRequest",
    "Blueprint",
    "Command",
    "Config",
    "Console",
    "Container",
    "Controller",
    "DB",
    "Env",
    "Extension",
    "Extensions",
    "Forbidden",
    "FormRequest",
    "HttpException",
    "Middleware",
    "Migration",
    "Migrator",
    "Model",
    "ModelNotFound",
    "NotFound",
    "QueryBuilder",
    "Request",
    "Response",
    "Route",
    "Rule",
    "Schema",
    "ServiceProvider",
    "Unauthorized",
    "ValidationException",
    "Validator",
    "View",
    "abort",
    "abort_if",
    "abort_unless",
    "app",
    "base_path",
    "config",
    "database_path",
    "env",
    "markup",
    "public_path",
    "redirect",
    "resource_path",
    "route",
    "storage_path",
    "validate",
    "view",
]
