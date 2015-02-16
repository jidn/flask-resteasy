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


# Add a dummy Resource to verify that the app is properly set.
class HelloWorld(Resource):
    resp = {}

    def get(self):
        return HelloWorld.resp


def to_json(v):
    return loads(v.data)


class TestPrefixes(object):
    """Ensure the Blueprint, Api, Resource sequence of prefix and url are right
    """
    resource_url = '/hi'
    prefix_params = [(None, None, ''), (None, '/url', '/url'),
                     ('/bp', None, '/bp'), ('/bp', '/api', '/bp/api')]

    @pytest.mark.parametrize('setup', prefix_params)
    def test_with_blueprint(self, setup):
        bp_prefix, api_prefix, bp_api_url = setup
        expecting_url = bp_api_url + TestPrefixes.resource_url

        bp = Blueprint('test', __name__, url_prefix=bp_prefix)
        api = Api(bp, prefix=api_prefix)
        api.add_resource(HelloWorld, TestPrefixes.resource_url, endpoint='hello')
        api.init_app(bp)
        app = Flask(__name__, static_folder=None)
        app.register_blueprint(bp)

        assert 'hello' in api.endpoints
        assert HelloWorld.endpoint == 'hello'
        with app.test_client() as c:
            rv = c.get(expecting_url)
            assert rv.status_code == 200
            assert request.endpoint == 'test.hello'

        with app.test_request_context(expecting_url):
            assert url_for('.hello') == expecting_url
            assert url_for('test.hello') == expecting_url
            assert api.url_for(HelloWorld) == expecting_url

    @pytest.mark.parametrize('setup', prefix_params)
    def test_with_ini_app_blueprint(self, setup):
        bp_prefix, api_prefix, bp_api_url = setup
        expecting_url = bp_api_url + TestPrefixes.resource_url

        bp = Blueprint('test', __name__, url_prefix=bp_prefix)
        api = Api(prefix=api_prefix)
        api.add_resource(HelloWorld, TestPrefixes.resource_url)
        api.init_app(bp)
        app = Flask(__name__, static_folder=None)
        app.register_blueprint(bp)

        assert 'helloworld' in api.endpoints
        assert HelloWorld.endpoint == 'helloworld'
        with app.test_client() as c:
            rv = c.get(expecting_url)
            assert rv.status_code == 200
            assert request.endpoint == 'test.helloworld'

        with app.test_request_context(expecting_url):
            assert url_for('.helloworld') == expecting_url
            assert url_for('test.helloworld') == expecting_url
            assert api.url_for(HelloWorld) == expecting_url


class TestAPIWithBlueprint(object):

    def test_add_with_app_blueprint(self):
        app = Flask(__name__)
        blueprint = Blueprint('test', __name__)
        app.register_blueprint(blueprint)
        with pytest.raises(ValueError) as err:
            api = Api(blueprint)
        assert err.value.message.startswith('Blueprint is already registered')

        app = Flask(__name__)
        blueprint = Blueprint('test', __name__)
        app.register_blueprint(blueprint)
        api = Api()
        api.add_resource(HelloWorld, '/hi')
        with pytest.raises(ValueError) as err:
            api.init_app(blueprint)
        assert err.value.message.startswith('Blueprint is already registered')

    def test_with_prefix(self):
        bp = Blueprint('test', __name__, url_prefix='/bp')
        api = Api(prefix='/api')
        api.add_resource(HelloWorld, '/hi')
        api.init_app(bp)
        app = Flask(__name__)
        app.register_blueprint(bp)

        assert api.prefix == '/api'
        with app.test_client() as c:
            assert to_json(c.get('/bp/api/hi')) == {}

    def test_add_resource_endpoint(self):
        blueprint = Blueprint('test', __name__)
        api = Api(blueprint)
        view = Mock(**{'as_view.return_value': Mock(__name__='test_view')})
        api.add_resource(view, '/foo', endpoint='bar')
        app = Flask(__name__)
        app.register_blueprint(blueprint)
        view.as_view.assert_called_with('bar')

    def test_add_resource_endpoint_after_registration(self):
        blueprint = Blueprint('test', __name__)
        api = Api(blueprint)
        app = Flask(__name__)
        app.register_blueprint(blueprint)
        view = Mock(**{'as_view.return_value': Mock(__name__='test_view')})
        api.add_resource(view, '/foo', endpoint='bar')
        view.as_view.assert_called_with('bar')

    def test_url_with_api_prefix(self):
        blueprint = Blueprint('test', __name__)
        api = Api(blueprint, prefix='/api')
        api.add_resource(HelloWorld, '/hi', endpoint='hello')
        app = Flask(__name__)
        app.register_blueprint(blueprint, url_prefix='/bp')
        with app.test_request_context('/bp/api/hi'):
            assert request.endpoint == 'test.hello'
            assert url_for('.hello') == '/bp/api/hi'

    def test_url_with_blueprint_prefix(self):
        app = Flask(__name__)
        blueprint = Blueprint('test', __name__, url_prefix='/bp')
        api = Api(blueprint)
        api.add_resource(HelloWorld, '/hi', endpoint='hello')
        app.register_blueprint(blueprint)
        with app.test_request_context('/bp/hi'):
            assert request.endpoint == 'test.hello'

    def test_url_with_registration_prefix(self):
        blueprint = Blueprint('test', __name__, url_prefix='/v1')
        api = Api(blueprint, prefix='/2015')
        api.add_resource(HelloWorld, '/hi', endpoint='hello')
        app = Flask(__name__)
        app.register_blueprint(blueprint)
        with app.test_request_context('/v1/2015/hi'):
            assert request.endpoint == 'test.hello'

    def test_registration_prefix_overrides_blueprint_prefix(self):
        blueprint = Blueprint('test', __name__, url_prefix='/bp')
        api = Api(blueprint, prefix='/api')
        api.add_resource(HelloWorld, '/hi', endpoint='hello')
        app = Flask(__name__)
        app.register_blueprint(blueprint, url_prefix='/reg')
        with app.test_request_context('/reg/api/hi'):
            assert request.endpoint == 'test.hello'

    def test_add_resource_kwargs(self):
        bp = Blueprint('bp', __name__)
        api = Api(bp)

        @api.resource('/foo', defaults={'foo': 'bar'})
        class Foo(Resource):
            def get(self, foo):
                return foo
        app = Flask(__name__)
        app.register_blueprint(bp)
        with app.test_client() as c:
            assert c.get('/foo').data == '"bar"'

    def test_resource_return_values(self):
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
            assert rv.data == '{}'
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
        app = Flask(__name__)
        app.config['DEBUG'] = True

        @app.errorhandler(ValueError)
        def value_error(err):
            return api.responder(({'err': err.message}, 500))

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
