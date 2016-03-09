"""API testing."""
try:
    from mock import Mock
except:
    # python3
    from unittest.mock import Mock
from flask import Flask, abort, make_response, request, url_for
from flask.json import loads
from flask_resteasy import Api, ApiResponse, Resource, JSONResponse, unpack
import pytest
from .tools import make_foo


def to_json(v):
    """Simple helper to get JSON from object."""
    return loads(v.data)


class TestHelpers(object):
    """Helper function to include in other classes."""

    def test_unpack(self):
        """Test unpack."""
        assert ('hi', 200, {}) == unpack('hi')
        assert ('hi', 200, {}) == unpack(('hi', 200))
        assert ('hi', 200, {}) == unpack(('hi', None))
        assert ('hi', 200, {'X': 'hi'}) == unpack(('hi', 200, {'X': 'hi'}))

    def test_resource_without_endpoint(self):
        """Resource without endpoint."""
        resource = make_foo()
        assert not hasattr(resource, 'endpoint')

    def test_using_ApiResponse(self):
        """ApiResponse must be subclassed."""
        with Flask(__name__).app_context():
            with pytest.raises(NotImplementedError) as err:
                ApiResponse().pack('hi', 200)
            assert err.value.args[0] == "You must subclass from ApiResponse."

    def test_json(self):
        """JSON response."""
        with Flask(__name__).app_context():
            resp = JSONResponse().pack('hi', 201)
            assert resp.status_code == 201
            assert resp.headers['Content-Type'] == 'application/json'
            assert loads(resp.data) == "hi"


class TestPrefixes(object):
    """Are Blueprint, Api, Resource sequence of prefix and url correct."""

    resource_url = '/hi'

    @pytest.mark.parametrize('api_prefix', [None, '/api'])
    def test_with_app(self, api_prefix):
        """API creation with different prefixes.

        API created with app.
        """
        expecting_url = (api_prefix or '') + TestPrefixes.resource_url
        resource = make_foo()
        app = Flask(__name__, static_folder=None)
        api = Api(app, prefix=api_prefix)
        api.add_resource(resource, TestPrefixes.resource_url, endpoint='hello')

        assert 'hello' in api.endpoints
        assert resource.endpoint == 'hello'
        with app.test_client() as c:
            rv = c.get(expecting_url)
            assert rv.status_code == 200
            assert request.endpoint == 'hello'

        with app.test_request_context(expecting_url):
            assert url_for('hello') == expecting_url
            assert api.url_for(resource) == expecting_url

    @pytest.mark.parametrize('api_prefix', [None, '/api'])
    def test_with_init_app(self, api_prefix):
        """API creation with different prefixes.

        API attached after app creation.
        """
        expecting_url = (api_prefix or '') + TestPrefixes.resource_url
        resource = make_foo()
        api = Api(prefix=api_prefix)
        api.add_resource(resource, TestPrefixes.resource_url, endpoint='hello')
        app = Flask(__name__, static_folder=None)
        api.init_app(app)

        assert 'hello' in api.endpoints
        assert resource.endpoint == 'hello'
        with app.test_client() as c:
            rv = c.get(expecting_url)
            assert rv.status_code == 200
            assert request.endpoint == 'hello'

        with app.test_request_context(expecting_url):
            assert url_for('hello') == expecting_url
            assert api.url_for(resource) == expecting_url


class TestAPI(object):
    """Test the API object.

    Is it working as expected?
    """

    def test_api(self):
        """Ensure endpoint is created."""
        app = Mock()
        app.configure_mock(**{'record.side_effect': AttributeError})
        api = Api(app, prefix='/foo')
        assert api.prefix == '/foo'

    def test_api_delayed_initialization(self):
        """API delayed initialization."""
        app = Flask(__name__)
        api = Api()
        resource = make_foo()
        api.add_resource(resource, '/', endpoint="hello")
        api.init_app(app)
        assert resource.endpoint == 'hello'
        with app.test_client() as client:
            assert client.get('/').status_code == 200

    def test_api_on_multiple_url(self):
        """Added resource can have several URLs.

        `url_for` will only return the first url
        """
        app = Flask(__name__, static_folder=None)
        api = Api(app)

        resource = make_foo()
        api.add_resource(resource, '/api', '/api2')
        with app.test_request_context('/api'):
            assert api.url_for(resource) == '/api'

        with app.test_request_context('/api2'):
            assert api.url_for(resource) == '/api'

        with app.test_client() as c:
            assert to_json(c.get('/api')) == resource.resp
            assert to_json(c.get('/api2')) == resource.resp

    def test_api_same_endpoint(self):
        """API reuse endpoint."""
        app = Flask(__name__)
        api = Api(app, prefix='/v1')

        api.add_resource(make_foo(), '/foo', endpoint='baz')

        class Bar(Resource):
            def get(self):
                return 'bar'
        with pytest.raises(ValueError) as err:
            api.add_resource(Bar, '/bar', endpoint='baz')
        assert err.value.args[0].startswith("Endpoint 'baz' is already")

    def test_api_same_url(self):
        """API same url."""
        # TODO Should this pop an error?
        app = Flask(__name__)
        api = Api(app, prefix='/v1')

        @api.resource('/api')
        class Foo(Resource):
            def get(self):
                return 'foo'

        @api.resource('/api')
        class Bar(Resource):
            def get(self):
                return 'bar'

        with app.test_request_context('/api'):
            assert url_for('foo') == url_for('bar')
            assert url_for('foo') == '/v1/api'
        with app.test_client() as c:
            rv = c.get('/v1/api')
            assert loads(rv.data) == "foo"

    def test_handle_api_error(self):
        """Handle API errors."""
        api = Api()

        @api.resource('/api', endpoint='api')
        class Test(Resource):
            def get(self):
                abort(404)

        app = Flask(__name__)
        app.config['DEBUG'] = True
        api.init_app(app)

        @app.errorhandler(404)
        def not_found(err):
            rv = {'code': 404, 'msg': 'Not found'}
            return api.responder.pack(rv, 404)

        with app.test_client() as c:
            rv = c.get("/api")
            assert rv.status_code == 404
            assert rv.headers['Content-Type'] == 'application/json'
            data = loads(rv.data.decode())
            assert data.get('code') == 404
            assert 'msg' in data

    def test_handle_non_api_error(self):
        """Handle non API errors."""
        app = Flask(__name__)
        Api(app)

        with app.test_client() as c:
            rv = c.get("/foo")
            assert rv.status_code == 404
            assert rv.headers['Content-Type'] == 'text/html'

    def test_url_for(self):
        """url_for test."""
        app = Flask(__name__)
        api = Api(app)
        resource = make_foo()
        api.add_resource(resource, '/greeting/<int:idx>')
        with app.test_request_context('/foo'):
            assert api.url_for(resource, idx=5) == '/greeting/5'

    def test_add_the_same_resource_on_different_endpoint(self):
        """Add resource on different endpoints.

        We should be able to add the same resource multiple times as long
        as we use different endpoints.
        """
        app = Flask(__name__)
        api = Api(app)
        app.config['DEBUG'] = True

        class Foo1(Resource):
            def get(self):
                return 'foo1'

        api.add_resource(Foo1, '/foo', endpoint='bar')
        api.add_resource(Foo1, '/foo/toto', endpoint='blah')

        with app.test_client() as client:
            foo1 = client.get('/foo')
            assert foo1.data == b'"foo1"'
            assert foo1.headers['Content-Type'] == 'application/json'

            foo2 = client.get('/foo/toto')
            assert foo2.data == b'"foo1"'

    def test_add_resource_endpoint(self):
        """Add resource endpoint."""
        app = Mock(Flask)
        app.view_functions = {}
        view = Mock()

        api = Api(app)
        api.output = Mock()
        api.add_resource(view, '/foo', endpoint='bar')

        view.as_view.assert_called_with('bar')

    def test_resource_decorator(self):
        """Resource decorator."""
        app = Flask(__name__)
        api = Api(app)

        @api.resource('/api')
        class Foo(Resource):
            def get(self):
                return 'foo'

        with app.test_client() as c:
            c.get('/api').data == 'foo'

    def test_add_resource_kwargs(self):
        """Add resource kwargs."""
        app = Flask(__name__)
        app.config['DEBUG'] = True
        api = Api(app)

        @api.resource('/bar', defaults={'foo': 'bar'})
        class Bar(Resource):
            def get(self, foo):
                return foo
        with app.test_client() as c:
            assert loads(c.get('/bar').data) == "bar"

    def test_output_unpack(self):
        """Output unpack for response."""
        def make_empty_response():
            return {'foo': 'bar'}

        app = Flask(__name__)
        api = Api(app)

        with app.test_request_context("/foo"):
            wrapper = api.output(make_empty_response)
            resp = wrapper()
            assert resp.status_code == 200
            assert resp.data.decode() == '{"foo": "bar"}'

    def test_output_func(self):
        """Output function."""
        def make_empty_response():
            return make_response('')

        app = Flask(__name__)
        api = Api(app)

        with app.test_request_context("/foo"):
            wrapper = api.output(make_empty_response)
            resp = wrapper()
            assert resp.status_code == 200
            assert resp.data.decode() == ''

    def test_resource(self):
        """Resource."""
        app = Flask(__name__)
        resource = Resource()
        resource.get = Mock()
        with app.test_request_context("/foo"):
            resource.dispatch_request()

    def test_resource_resp(self):
        """Resource response."""
        app = Flask(__name__)
        resource = Resource()
        resource.get = Mock()
        with app.test_request_context("/foo"):
            resource.get.return_value = make_response('')
            resource.dispatch_request()

    def test_resource_error(self):
        """Unimplemented method."""
        app = Flask(__name__)
        resource = Resource()
        with app.test_request_context("/foo"):
            with pytest.raises(AssertionError) as err:
                resource.dispatch_request()
            assert err.value.args[0].startswith('Unimplemented method')

    def test_resource_head(self):
        """Check for a HEAD."""
        app = Flask(__name__)
        resource = Resource()
        with app.test_request_context("/foo", method="HEAD"):
            with pytest.raises(AssertionError):
                resource.dispatch_request()

    def test_fr_405(self):
        """HTTP 405 response."""
        app = Flask(__name__)
        api = Api(app)
        foo = make_foo()
        api.add_resource(foo, '/ids/<int:id>', endpoint="hello")
        with app.test_client() as c:
            rv = c.post('/ids/3')
            assert rv.status_code == 405
        expected_methods = ['HEAD', 'OPTIONS'] + foo.methods
        assert rv.headers.get_all('Allow').sort() == expected_methods.sort()


class TestJSON(object):
    """Testing JSON response."""

    def test_will_pass_options_to_json(self):
        """Are we getting JSON."""
        resource = make_foo()
        app = Flask(__name__)
        api = Api(app, response=JSONResponse(indent=123))
        api.add_resource(resource, '/foo', endpoint='bar')

        assert 'indent' in api.responder.json_settings
        with app.test_client() as client:
            rv = client.get('/foo')
            lines = rv.data.splitlines()
            lines = [line.decode() for line in lines]
            assert lines[0] == "{"
            assert lines[1].startswith(' ' * 123) is True
            assert lines[2] == "}"

    @pytest.mark.xfail
    def test_datetime(self):
        """Testing datetime.

        What do I expect the datetime.datetime to be? rfc822, iso?
        """
        assert False
