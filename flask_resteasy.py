"""Automate the setup of pluggable views.

Specifically :class:`flask.views.MethodView` for use in creating JSON
REST APIs. Other response types could also be create from ApiResponse.

Unlike Flask-RESTful, this does not marshal values or validate input or
catch and process error messages.  There are other existing tools that
solve the problem better and Flask really is about flexibility.

EXAMPLE
    from flask import Flask
    from flask.ext import resteasy

    app = Flask(__name__)
    api = resteasy.Api(app)

    @api.resource('/')
    class HelloWorld(resteasy.Resource):
        def get(self):
            return {'msg': 'Hello world'}

        def delete(self):
            return {'msg': 'No can do'}

    if __name__ == '__main__':
        app.run(debug=True)
"""

from types import MethodType
from itertools import chain
from functools import partial, wraps
import flask
from flask.json import dumps
from flask.views import MethodView as Resource
from flask.helpers import _endpoint_from_view_func
from werkzeug.wrappers import Response as ResponseBase


__version__ = "0.0.7"


def unpack(rv):
    """Unpack the response from a view.

    :param rv: the view response
    :type rv: either a :class:`werkzeug.wrappers.Response` or a
        tuple of (data, status_code, headers)

    """
    if isinstance(rv, ResponseBase):
        return rv

    status = headers = None
    if isinstance(rv, tuple):
        rv, status, headers = rv + (None,) * (3 - len(rv))

    if rv is None:
        raise ValueError('View function did not return a response')

    if status is None:
        status = 200
    return rv, status, headers or {}


class Api(object):
    """The main entry point for the application.

    You need to initialize it with a Flask Application: ::

    >>> app = flask.Flask(__name__)
    >>> api = flask_resteasy.Api(app)

    Alternatively, you can use :meth:`init_app` to set the Flask application
    after it has been constructed.

    >>> api.init_app(app)
    """

    def __init__(self, app=None, prefix='', decorators=None, response=None):
        """Create and API consisting of one or more resources.

        :param app: the Flask application or blueprint object
        :type app: :class:`~flask.Flask` or :class:`~flask.Blueprint`
        :param prefix: Prefix all routes with a value, eg /v1 or /2015-01-01
        :type prefix: str
        :param decorators: Decorators to attach to every resource
        :type decorators: list
        :param response: `ApiResponse` object, default JSONResponse()
        :type response: `ApiResponse`
        """
        self.app = None
        self.blueprint = None
        self.blueprint_setup = None
        self.prefix = prefix
        self.resources = []
        self.endpoints = set()
        self.decorators = decorators if decorators else []
        self.responder = response if response else JSONResponse()

        if app is not None:
            self.app = app
            self.init_app(app)

    def init_app(self, app):
        """Initialize actions with the app or blueprint.

        :param app: the Flask application or blueprint object
        :type app: :class:`~flask.Flask` or :class:`~flask.Blueprint`

        Examples::

            api = Api()
            api.add_resource(...)
            api.init_app(blueprint)
        """
        try:
            # Assume this is a blueprint and defer initialization
            if app._got_registered_once is True:
                raise ValueError("""Blueprint is already registered with an app.""")
            app.record(self._deferred_blueprint_init)
        except AttributeError:
            self._init_app(app)
        else:
            self.blueprint = app

    def _init_app(self, app):
        """Initialize actions with the given :class:`flask.Flask` object.

        :param app: The flask application object
        :type app: :class:`~flask.Flask`
        """
        for resource, urls, kwargs in self.resources:
            self._register_view(app, resource, *urls, **kwargs)

    def _deferred_blueprint_init(self, setup_state):
        """Bind resources to the app as recorded in blueprint.

        Synchronize prefix between blueprint/api and registration options, then
        perform initialization with setup_state.app :class:`flask.Flask` object.
        When a :class:`flask.ext.resteasy.Api` object is initialized with a blueprint,
        this method is recorded on the blueprint to be run when the blueprint is later
        registered to a :class:`flask.Flask` object.  This method also monkeypatches
        BlueprintSetupState.add_url_rule with _add_url_rule_patch.

        :param setup_state: The setup state object passed to deferred functions
            during blueprint registration
        :type setup_state: :class:`flask.blueprints.BlueprintSetupState`
        """
        self.blueprint_setup = setup_state
        if setup_state.add_url_rule.__name__ != '_add_url_rule_patch':
            setup_state._original_add_url_rule = setup_state.add_url_rule
            setup_state.add_url_rule = MethodType(Api._add_url_rule_patch,
                                                  setup_state)
        if not setup_state.first_registration:
            raise ValueError('flask-RESTEasy blueprints can only be registered once.')
        self._init_app(setup_state.app)

    def resource(self, *urls, **kwargs):
        """Add a :class:`~flask_resteasy.Resource` class.

        See :meth:`~flask_resteasy.Api.add_resource`

        Example::

            app = Flask(__name__)
            api = resteasy.Api(app)

            @api.resource('/foo')
            class Foo(Resource):
                def get(self):
                    return {'msg': 'Hello, World!'}
        """
        def decorator(cls):
            self.add_resource(cls, *urls, **kwargs)
            return cls

        return decorator

    def add_resource(self, resource, *urls, **kwargs):
        """Add a resource to the api.

        :param resource: the class name of your resource
        :type resource: :class:`Resource`
        :param urls: one or more url routes to match the resource, standard
                     flask routing rules apply.  Any url variables will be
                     passed to the resource method as args.
                     With multiple urls, :meth:`Api.url_for` fives the first
        :type urls: str

        :param endpoint: endpoint name (defaults to :meth:`Resource.__name__.lower`
            Can be used to reference this route in :class:`fields.Url` fields
        :type endpoint: str
        :param decorators: add decorators to MethodView.decorators
        :type decorators: sequence

        Additional keyword arguments not specified above will be passed as-is
        to :meth:`flask.Flask.add_url_rule`.

        Examples::

        >>> api.add_resource(Foo, '/', '/hello')
        >>> api.add_resource(Foo, '/foo', endpoint="foo")
        >>> api.add_resource(FooSpecial, '/special/foo', endpoint="foo")

        SIDE EFFECT
            Assign endpoint to the resource if it isn't already defined
            which can be used for :func:`flask.url_for`.
            Thus Foo.endpoint is 'foo'
        >>> Foo.endpoint
        'foo'
        >>> Foo.url_for()
        '/foo'
        """
        if self.app is not None:
            self._register_view(self.app, resource, *urls, **kwargs)
        else:
            self.resources.append((resource, urls, kwargs))

    def _register_view(self, app, resource, *urls, **kwargs):
        """Bind resources to the app.

        :param app: an actual :class:`flask.Flask` app
        :param resource:
        :param urls:

        :param endpoint: endpoint name (defaults to :meth:`Resource.__name__.lower`
            Can be used to reference this route in :meth:`flask.url_for`
        :type endpoint: str

        Additional keyword arguments not specified above will be passed as-is
        to :meth:`flask.Flask.add_url_rule`.

        SIDE EFFECT
            Implements the one mentioned in add_resource
        """
        endpoint = kwargs.pop('endpoint', None) or resource.__name__.lower()
        self.endpoints.add(endpoint)

        if not isinstance(app, flask.Blueprint) and endpoint in app.view_functions.keys():
            existing_view_class = app.view_functions[endpoint].__dict__['view_class']

            # if you override the endpoint with a different class, avoid the collision by raising an exception
            if existing_view_class != resource:
                raise ValueError('Endpoint {!r} is already set to {!r}.'
                                 .format(endpoint, existing_view_class.__name__))

        if not hasattr(resource, 'endpoint'):  # Don't replace existing endpoint
            resource.endpoint = endpoint
        resource_func = self.output(resource.as_view(endpoint))

        for decorator in chain(kwargs.pop('decorators', ()), self.decorators):
            resource_func = decorator(resource_func)

        for url in urls:
            rule = self._make_url(url, self.blueprint.url_prefix if self.blueprint else None)

            # If this Api has a blueprint
            if self.blueprint:
                # And this Api has been setup
                if self.blueprint_setup:
                    # Set the rule to a string directly, as the blueprint
                    # is already set up.
                    self.blueprint_setup.add_url_rule(self._make_url(url, None), view_func=resource_func, **kwargs)
                    continue
                else:
                    # Set the rule to a function that expects the blueprint
                    # prefix to construct the final url.  Allows deferment
                    # of url finalization in the case that the Blueprint
                    # has not yet been registered to an application, so we
                    # can wait for the registration prefix
                    rule = partial(self._make_url, url)
            else:
                # If we've got no Blueprint, just build a url with no prefix
                rule = self._make_url(url, None)
            # Add the url to the application or blueprint
            app.add_url_rule(rule, view_func=resource_func, **kwargs)

    @staticmethod
    def _add_url_rule_patch(blueprint_setup, rule, endpoint=None, view_func=None, **options):
        """Patch BlueprintSetupState.add_url_rule for delayed creation.

        Method used for setup state instance corresponding to this Api
        instance.  Exists primarily to enable _make_url's function.

        :param blueprint_setup: The BlueprintSetupState instance (self)
        :param rule: A string or callable that takes a string and returns a
            string(_make_url) that is the url rule for the endpoint
            being registered
        :param endpoint: See :meth:`flask.BlueprintSetupState.add_url_rule`
        :param view_func: See :meth:`flask.BlueprintSetupState.add_url_rule`
        :param **options: See :meth:`flask.BlueprintSetupState.add_url_rule`
        """
        if callable(rule):
            rule = rule(blueprint_setup.url_prefix)
        elif blueprint_setup.url_prefix:
            rule = blueprint_setup.url_prefix + rule
        options.setdefault('subdomain', blueprint_setup.subdomain)
        if endpoint is None:
            endpoint = _endpoint_from_view_func(view_func)
        defaults = blueprint_setup.url_defaults
        if 'defaults' in options:
            defaults = dict(defaults, **options.pop('defaults'))
        blueprint_setup.app.add_url_rule(rule, '%s.%s' % (blueprint_setup.blueprint.name, endpoint),
                                         view_func, defaults=defaults, **options)

    def output(self, resource):
        """Wrap a resource (as a flask view function).

        This is for cases where the resource does not directly return
        a response object. Now everything should be a Response object.

        :param resource: The resource as a flask view function
        """
        @wraps(resource)
        def wrapper(*args, **kwargs):
            rv = resource(*args, **kwargs)
            rv = self.responder(rv)
            return rv

        return wrapper

    def _make_url(self, url_part, blueprint_prefix):
        """Create URL from blueprint_prefix, api prefix and resource url.

        This method is used to defer the construction of the final url in
        the case that the Api is created with a Blueprint.

        :param url_part: The part of the url the endpoint is registered with
        :param blueprint_prefix: The part of the url contributed by the
            blueprint.  Generally speaking, BlueprintSetupState.url_prefix
        """
        parts = (blueprint_prefix, self.prefix, url_part)
        return ''.join(_ for _ in parts if _)

    def url_for(self, resource, **kwargs):
        """Create a url for the given resource.

        :param resource: The resource
        :type resource: :class:`Resource`
        :param kwargs: Same arguments you would give :class:`flask.url_for`
        """
        if self.blueprint:
            return flask.url_for('.' + resource.endpoint, **kwargs)
        return flask.url_for(resource.endpoint, **kwargs)


class ApiResponse(object):
    """Prototype for creating response from MethodView call.

    Subclass to create a response handler.  See :class:`JSONResponse`
    """

    content_type = None

    def __call__(self, rv):
        """Return json from given tuple.

        :param rv: Return value from a view
        :type rv: a tuple or :class:`~flask.Response`. The tuple is
            (data, status_code=200, headers={})
        :return: :class:`~flask.Response`
        """
        raise NotImplementedError("You must subclass from ApiResponse.")

    def pack(self, data, status_code=200, headers={}):
        """Return a response from :class:`flask.views.MethodView` method.

        :return See `__call__`
        """
        return self((data, status_code, headers))


class JSONResponse(ApiResponse):
    """JSON response creator."""

    autocorrect_location_header = False
    content_type = 'application/json'

    def __init__(self, encoder=None, **kwargs):
        """Create a JSON response maker.

        :param encoder: JSON encoder, defaults to meth:`json.dumps`
        Any other arguments are passed directly to `encoder`
        """
        if encoder is None:
            encoder = dumps
        self.json_settings = kwargs
        self._encoder = encoder

    def __call__(self, rv):
        """Return json response from given tuple.

        :param rv: Return value from a view
        :type rv: a tuple or :class:`~flask.Response`
        :return: :class:`~flask.Response`
        """
        if isinstance(rv, ResponseBase):
            return rv
        data, status, headers = unpack(rv)
        resp = flask.make_response(self._encoder(data, **self.json_settings),
                                   status, {'Content-Type': self.content_type})
        resp.headers.extend(headers)
        return resp

