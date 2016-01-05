"""Testing blueprints with API."""
try:
    from mock import Mock
except:
    # python3
    from unittest.mock import Mock
import pytest
import warnings
from flask import Flask, Blueprint, request, url_for
from flask.json import loads
from flask_resteasy import Api, Resource
from .tools import make_foo


def setup_blueprint_api(resource, bp=None, ap=None, rp=None):
    """Create blueprint then API."""
    blueprint = Blueprint('test', __name__, url_prefix=bp)
    api = Api(blueprint, prefix=ap)
    api.add_resource(resource, '/foo', endpoint='foo')
    app = Flask(__name__, static_folder=None)
    app.register_blueprint(blueprint, url_prefix=rp)
    return app, api


def setup_api_blueprint(resource, bp=None, ap=None, rp=None):
    """Create API without blueprint, then init with blueprint."""
    api = Api(None, prefix=ap)
    api.add_resource(resource, '/foo', endpoint='foo')
    blueprint = Blueprint('test', __name__, url_prefix=bp)
    api.init_app(blueprint)
    app = Flask(__name__, static_folder=None)
    app.register_blueprint(blueprint, url_prefix=rp)
    # It should fail if tried again
    with pytest.raises(ValueError) as e_info:
        app.register_blueprint(blueprint, url_prefix=rp)
    assert e_info.value.message.endswith("only be registered once.")
    return app, api


class TestBlueprint(object):
    """Test blueprints.

    Ensure the Blueprint, Api, Resource sequence of prefix and url are right
    """

    prefix_params = (
        (None, None, None, '/foo'),
        ('/bp', None, None, '/bp/foo'),
        ('/v1', '/2015', None, '/v1/2015/foo'),
        ('/bp', '/api', '/reg', '/reg/api/foo'),
        )

    def test_add_with_app_blueprint(self):
        """Add with app blueprint."""
        app = Flask(__name__)
        blueprint = Blueprint('test', __name__)
        app.register_blueprint(blueprint)
        with pytest.raises(ValueError) as err:
            api = Api(blueprint)
        assert err.value.args[0].startswith('Blueprint is already registered')

        app = Flask(__name__)
        blueprint = Blueprint('test', __name__)
        app.register_blueprint(blueprint)
        api = Api()
        resource = make_foo()
        api.add_resource(resource, '/hi')
        with pytest.raises(ValueError) as err:
            api.init_app(blueprint)
        assert err.value.args[0].startswith('Blueprint is already registered')

    def test_add_resource_endpoint(self):
        """Add resource endpoint."""
        blueprint = Blueprint('test', __name__)
        api = Api(blueprint)
        view = Mock(**{'as_view.return_value': Mock(__name__='test_view')})
        api.add_resource(view, '/foo', endpoint='bar')
        app = Flask(__name__)
        app.register_blueprint(blueprint)
        view.as_view.assert_called_with('bar')

    def test_add_resource_endpoint_after_registration(self):
        """Add resource endpoint after registration."""
        blueprint = Blueprint('test', __name__)
        api = Api(blueprint)
        app = Flask(__name__)
        app.register_blueprint(blueprint)
        view = Mock(**{'as_view.return_value': Mock(__name__='test_view')})
        api.add_resource(view, '/foo', endpoint='bar')
        view.as_view.assert_called_with('bar')

    @pytest.mark.parametrize('setup', (setup_blueprint_api,
                                       setup_api_blueprint))
    @pytest.mark.parametrize('bp,ap,rp,url', prefix_params)
    def test_prefix(self, bp, ap, rp, url, setup):
        """Test various prefix possibilities with blueprint available.

        at Api creation time.
        bp: Blueprint(..., url_prefix=bp)
        ap: Api(..., prefix=ap)
        rp: app.register_blueprint(..., url_prefix=rp)
        """
        resource = make_foo()
        app, api = setup(resource, bp, ap, rp)

        assert 'foo' in api.endpoints
        assert resource.endpoint == 'foo'
        with app.test_request_context(url):
            assert request.endpoint == 'test.foo'
            assert url_for('.foo') == url
            assert url_for(request.endpoint) == url
            assert api.url_for(resource) == url

        with app.test_client() as c:
            rv = c.get(url)
            assert rv.status_code == 200
            assert request.endpoint == 'test.foo'
            assert loads(rv.data) == resource.resp

    def test_add_resource_kwargs(self):
        """add resource kwargs."""
        bp = Blueprint('bp', __name__)
        api = Api(bp)

        @api.resource('/foo', defaults={'foo': 'bar'})
        class Foo(Resource):
            def get(self, foo):
                return foo
        app = Flask(__name__)
        app.register_blueprint(bp)
        with app.test_client() as c:
            assert loads(c.get('/foo').data) == "bar"

    def test_resource_return_values(self):
        """resource return values."""
        app = Flask(__name__)
        app.config['DEBUG'] = True
        api = Api(app)

        @api.resource('/api/<int:k>')
        class Foo(Resource):
            def get(self, k):
                if k == 0:
                    return {}, 302, {'X-Junk': 'junk header'}
                elif k == 1:
                    return api.responder(({'msg': 'no way'}, 403))

        with app.test_client() as c:
            rv = c.get('/api/0')
            assert rv.status_code == 302
            assert loads(rv.data) == {}
            assert rv.headers['X-junk'] == 'junk header'

            rv = c.get('/api/1')
            assert rv.status_code == 403
            data = loads(rv.data)
            assert data == {'msg': 'no way'}

            if app.debug is False:
                # if app.config['DEBUG'] = True you get
                # ValueError('View function did not return a response')
                rv = c.get('/api/2')
                assert rv.status_code == 500
                assert rv.headers['Content-Type'] == 'text/html'
            else:
                warnings.warn("skipping tests as flask app is DEBUG")

    def test_resource_exception_response(self):
        """resource exception response."""
        app = Flask(__name__)
        app.config['DEBUG'] = True

        @app.errorhandler(ValueError)
        def value_error(err):
            return api.responder(({'err': err.args[0]}, 500))

        api = Api(app)

        @api.resource('/api')
        class Foo(Resource):
            def get(self):
                return None

        with app.test_client() as c:
            rv = c.get('/api')
            assert rv.status_code == 500
            data = loads(rv.data)
            assert data['err'].endswith('not return a response')
