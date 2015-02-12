"""Automate the setup of pluggable views, specifically
:class:`flask.views.MethodView` for use in creating JSON REST APIs.

Unlike Flask-RESTful, this does not marshal values or validate input or
catch and process error messages.  There are other existing tools that
solve the problem better and Flask really is about flexibility.
"""
import pytest
from types import MethodType
from functools import partial, wraps
from werkzeug.wrappers import Response as ResponseBase
import flask
from flask.helpers import _endpoint_from_view_func
from flask.json import dumps
from flask.views import MethodView

def make_json_response(data, status_code=200, headers={}):
    """Create a JSON encoded :class:`~flask.Response`
    :return See `json_response`
    """
    return json_response((data, status_code, headers))

def json_response(rv):
    """Create a json response
    :param rv: Return value from a view
    :type rv: a tuple or :class:`~flask.Response`
    :return: :class:`~flask.Response`
    """
    if isinstance(rv, ResponseBase):
        return rv
    data, status, headers = unpack(rv)
    resp = flask.make_response(dumps(data), status, {'Content-Type': 'application/json'})
    resp.headers.extend(headers)
    return resp

def unpack(rv):
    """Unpack the response from a view
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
    >>> api = flask.ext.resteasy.Api(app)

    Alternatively, you can use :meth:`init_app` to set the Flask application
    after it has been constructed.

    >>> api.init_app(app)
    """

    def __init__(self, app=None, prefix='', decorators=None, response=json_response):
        """
        :param app: the Flask application or blueprint object
        :type app: :class:`~flask.Flask` or :class:`~flask.Blueprint`
        :param prefix: Prefix all routes with a value, eg /v1 or /2015-01-01
        :type prefix: str
        :param decorators: Decorators to attach to every resource
        :type decorators: list
        :param response: Create a view response
        :type response: function
        """
        self.app = None
        self.blueprint = None
        self.blueprint_setup = None
        self.prefix = prefix
        self.resources = []
        self.endpoints = set()
        self.decorators = decorators if decorators else []
        self.make_response = response

        if app is not None:
            self.app = app
            self.init_app(app)

    def init_app(self, app):
        """Initialize this class with the given :class:`flask.Flask`
        application or :class:`flask.Blueprint` object.

        :param app: the Flask application or blueprint object
        :type app: :class:`~flask.Flask` or :class:`~flask.Blueprint`

        Examples::

            api = Api()
            api.add_resource(...)
            api.init_app(blueprint)
        """
        try:
            # Assume this is a blueprint and defer initialization
            app.record(self._deferred_blueprint_init)
        except AttributeError:
            self._init_app(app)
        else:
            self.blueprint = app

    def _init_app(self, app):
        """Perform initialization actions with the given :class:`flask.Flask`
        object.

        :param app: The flask application object
        :type app: :class:`~flask.Flask`
        """
        for resource, urls, kwargs in self.resources:
            self._register_view(app, resource, *urls, **kwargs)

    def _deferred_blueprint_init(self, setup_state):
        """Synchronize prefix between blueprint/api and registration options, then
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
            raise ValueError('flask-resteasy blueprints can only be registered once.')
        self._init_app(setup_state.app)


    def add_resource(self, resource, *urls, **kwargs):
        """Adds a resource to the api.

        :param resource: the class name of your resource
        :type resource: :class:`Resource`
        :param urls: one or more url routes to match for the resource, standard
                     flask routing rules apply.  Any url variables will be
                     passed to the resource method as args.
        :type urls: str

        :param endpoint: endpoint name (defaults to :meth:`Resource.__name__.lower`
            Can be used to reference this route in :class:`fields.Url` fields
        :type endpoint: str
        :param decorators: add decorators to MethodView.decorators
        :type decorators: sequence

        Additional keyword arguments not specified above will be passed as-is
        to :meth:`flask.Flask.add_url_rule`.

        Examples::

            api.add_resource(HelloWorld, '/', '/hello')
            api.add_resource(Foo, '/foo', endpoint="foo")
            api.add_resource(FooSpecial, '/special/foo', endpoint="foo")
        """
        try:
            resource.decorators.extend(kwargs.pop('decorators'))
        except KeyError:
            pass
        if self.app is not None:
            self._register_view(self.app, resource, *urls, **kwargs)
        else:
            self.resources.append((resource, urls, kwargs))

    def resource(self, *urls, **kwargs):
        """Wraps a :class:`~flask_resteasy.Resource` class, adding it to the
        api. Parameters are the same as :meth:`~flask_resteasy.Api.add_resource`.

        Example::

            app = Flask(__name__)
            api = resteasy.Api(app)

            @api.resource('/foo')
            class Foo(Resource):
                def get(self):
                    return {'msg: 'Hello, World!'}
        """
        def decorator(cls):
            self.add_resource(cls, *urls, **kwargs)
            return cls
        return decorator

    def _register_view(self, app, resource, *urls, **kwargs):
        endpoint = kwargs.pop('endpoint', None) or resource.__name__.lower()
        self.endpoints.add(endpoint)

        if endpoint in app.view_functions.keys():
            existing_view_class = app.view_functions[endpoint].__dict__['view_class']

            # if you override the endpoint with a different class, avoid the collision by raising an exception
            if existing_view_class != resource:
                raise ValueError('Endpoint {!r} is already set to {!r}.'
                                 .format(endpoint, existing_view_class.__name__))

        # TODO this should be the complete endpoint, ie "blueprint.endpoint"
        resource.endpoint = endpoint
        resource_func = self.output(resource.as_view(endpoint))

        for decorator in self.decorators:
            resource_func = decorator(resource_func)

        for url in urls:
            # If this Api has a blueprint
            if self.blueprint:
                # And this Api has been setup
                if self.blueprint_setup:
                    # Set the rule to a string directly, as the blueprint is already
                    # set up.
                    #self.blueprint_setup.add_url_rule(url, view_func=resource_func, **kwargs)
                    self.blueprint_setup.add_url_rule(partial(self._make_url, url),
                                                      view_func=resource_func, **kwargs)
                    continue
                else:
                    # Set the rule to a function that expects the blueprint prefix
                    # to construct the final url.  Allows deferment of url finalization
                    # in the case that the associated Blueprint has not yet been
                    # registered to an application, so we can wait for the registration
                    # prefix
                    rule = partial(self._make_url, url)
            else:
                # If we've got no Blueprint, just build a url with no prefix
                rule = self._make_url(url, None)
            # Add the url to the application or blueprint
            app.add_url_rule(rule, view_func=resource_func, **kwargs)

    @staticmethod
    def _add_url_rule_patch(blueprint_setup, rule, endpoint=None, view_func=None, **options):
        """Method used to patch BlueprintSetupState.add_url_rule for setup
        state instance corresponding to this Api instance.  Exists primarily
        to enable _make_url's function.

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
        """Wraps a resource (as a flask view function), for cases where the
        resource does not directly return a response object.
        Now everything should be a Response object

        :param resource: The resource as a flask view function
        """
        @wraps(resource)
        def wrapper(*args, **kwargs):
            rv = resource(*args, **kwargs)
            rv = self.make_response(rv)
            return rv
        return wrapper

    def _make_url(self, url_part, blueprint_prefix):
        """This method is used to defer the construction of the final url in
        the case that the Api is created with a Blueprint.

        :param url_part: The part of the url the endpoint is registered with
        :param blueprint_prefix: The part of the url contributed by the
            blueprint.  Generally speaking, BlueprintSetupState.url_prefix
        """
        parts = (blueprint_prefix, self.prefix, url_part)
        return ''.join(_ for _ in parts if _)

    def url_for(self, resource, **kwargs):
        """Create a url for the given resource
        :param kwargs: Same arguments you would give :class:`flask.url-for`
        """
        return flask.url_for(resource.endpoint, **kwargs)


class Resource(MethodView):
    """
    Represents an abstract RESTeasy resource. Concrete resources should
    extend from this class and expose methods for each supported HTTP
    method: get, post, delete, put, and patch . If a resource is invoked
    without a supported HTTP method, the API will return with a status
    405 Method Not Allowed. Otherwise the appropriate method is called
    and passed all arguments from the url rule used when adding the
    resource to an Api instance. See
    :meth:`~flask.ext.resteasy.Api.add_resource` for details.
    """
    def dispatch_request(self, *args, **kwargs):
        assert len(self.decorators) == len(set(self.decorators)), \
            'Multiple decorator calls %s' % self.decorators
        rv = MethodView.dispatch_request(self, *args, **kwargs)
        return rv
