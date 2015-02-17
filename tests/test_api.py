try:
    from mock import Mock
except:
    # python3
    from unittest.mock import Mock
from flask import Flask, abort, make_response, request, url_for, views
from flask.json import loads
from flask_resteasy import Api, ApiResponse, Resource, JSONResponse, unpack
import pytest


def to_json(v):
    return loads(v.data)


# Add a dummy Resource to verify that the app is properly set.
class Foo(Resource):
    resp = {'msg': 'foo!'}

    def get(self):
        return Foo.resp


class TestHelpers(object):
    def test_unpack(self):
        assert ('hi', 200, {}) == unpack('hi')
        assert ('hi', 200, {}) == unpack(('hi', 200))
        assert ('hi', 200, {}) == unpack(('hi', None))
        assert ('hi', 200, {'X': 'hi'}) == unpack(('hi', 200, {'X': 'hi'}))

    def test_using_ApiResponse(self):
        with Flask(__name__).app_context():
            with pytest.raises(NotImplementedError) as err:
                ApiResponse().pack('hi', 200)
            assert err.value.message == "You must subclass from ApiResponse."

    def test_json(self):
        with Flask(__name__).app_context():
            resp = JSONResponse().pack('hi', 201)
            assert resp.status_code == 201
            assert resp.headers['Content-Type'] == 'application/json'
            assert resp.data == '"hi"'


class TestPrefixes(object):
    """Ensure the Blueprint, Api, Resource sequence of prefix and url are right
    """
    resource_url = '/hi'

    @pytest.mark.parametrize('api_prefix', [None, '/api'])
    def test_with_app(self, api_prefix):
        expecting_url = (api_prefix or '') + TestPrefixes.resource_url

        app = Flask(__name__, static_folder=None)
        api = Api(app, prefix=api_prefix)
        api.add_resource(Foo, TestPrefixes.resource_url, endpoint='hello')

        assert 'hello' in api.endpoints
        assert Foo.endpoint == 'hello'
        with app.test_client() as c:
            rv = c.get(expecting_url)
            assert rv.status_code == 200
            assert request.endpoint == 'hello'

        with app.test_request_context(expecting_url):
            assert url_for('hello') == expecting_url
            assert api.url_for(Foo) == expecting_url

    @pytest.mark.parametrize('api_prefix', [None, '/api'])
    def test_with_init_app(self, api_prefix):
        expecting_url = (api_prefix or '') + TestPrefixes.resource_url

        api = Api(prefix=api_prefix)
        api.add_resource(Foo, TestPrefixes.resource_url, endpoint='hello')
        app = Flask(__name__, static_folder=None)
        api.init_app(app)

        assert 'hello' in api.endpoints
        assert Foo.endpoint == 'hello'
        with app.test_client() as c:
            rv = c.get(expecting_url)
            assert rv.status_code == 200
            assert request.endpoint == 'hello'

        with app.test_request_context(expecting_url):
            assert url_for('hello') == expecting_url
            assert api.url_for(Foo) == expecting_url


class TestAPI(object):

    def test_api(self):
        app = Mock()
        app.configure_mock(**{'record.side_effect': AttributeError})
        api = Api(app, prefix='/foo')
        assert api.prefix == '/foo'

    def test_api_delayed_initialization(self):
        app = Flask(__name__)
        api = Api()
        api.add_resource(Foo, '/', endpoint="hello")
        api.init_app(app)
        assert Foo.endpoint == 'hello'
        with app.test_client() as client:
            assert client.get('/').status_code == 200

    def test_api_on_multiple_url(self):
        app = Flask(__name__)
        api = Api(app)

        api.add_resource(Foo, '/api', '/api2')
        with app.test_request_context('/api'):
            assert api.url_for(Foo) == '/api'
        with app.test_request_context('/api2'):
            assert api.url_for(Foo) == '/api'
        with app.test_client() as c:
            assert to_json(c.get('/api')) == Foo.resp
            assert to_json(c.get('/api2')) == Foo.resp

    def test_api_same_endpoint(self):
        app = Flask(__name__)
        api = Api(app, prefix='/v1')

        api.add_resource(Foo, '/foo', endpoint='baz')

        class Bar(Resource):
            def get(self):
                return 'bar'
        with pytest.raises(ValueError) as err:
            api.add_resource(Bar, '/bar', endpoint='baz')
        assert err.value.message.startswith("Endpoint 'baz' is already")

    def test_api_same_url(self):
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
            assert rv.data == '"foo"'

    def test_handle_api_error(self):
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
        app = Flask(__name__)
        Api(app)

        with app.test_client() as c:
            rv = c.get("/foo")
            assert rv.status_code == 404
            assert rv.headers['Content-Type'] == 'text/html'

    def test_url_for(self):
        app = Flask(__name__)
        api = Api(app)
        api.add_resource(Foo, '/greeting/<int:idx>')
        with app.test_request_context('/foo'):
            assert api.url_for(Foo, idx=5) == '/greeting/5'

    def test_add_the_same_resource_on_different_endpoint(self):
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

    def test_add_resource(self):
        app = Mock(Flask)
        app.view_functions = {}

        api = Api(app)
        api.output = Mock()
        api.add_resource(views.MethodView, '/foo')

        app.add_url_rule.assert_called_with('/foo', view_func=api.output())

    def test_add_resource_endpoint(self):
        app = Mock(Flask)
        app.view_functions = {}
        view = Mock()

        api = Api(app)
        api.output = Mock()
        api.add_resource(view, '/foo', endpoint='bar')

        view.as_view.assert_called_with('bar')

    def test_resource_decorator(self):
        app = Flask(__name__)
        api = Api(app)

        @api.resource('/api')
        class Foo(Resource):
            def get(self):
                return 'foo'

        with app.test_client() as c:
            c.get('/api').data == 'foo'

    def test_add_resource_kwargs(self):
        app = Flask(__name__)
        app.config['DEBUG'] = True
        api = Api(app)

        @api.resource('/bar', defaults={'foo': 'bar'})
        class Bar(Resource):
            def get(self, foo):
                return foo
        with app.test_client() as c:
            assert c.get('/bar').data == '"bar"'

    def test_output_unpack(self):
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

        def make_empty_resposne():
            return make_response('')

        app = Flask(__name__)
        api = Api(app)

        with app.test_request_context("/foo"):
            wrapper = api.output(make_empty_resposne)
            resp = wrapper()
            assert resp.status_code == 200
            assert resp.data.decode() == ''

    def test_resource(self):
        app = Flask(__name__)
        resource = Resource()
        resource.get = Mock()
        with app.test_request_context("/foo"):
            resource.dispatch_request()

    def test_resource_resp(self):
        app = Flask(__name__)
        resource = Resource()
        resource.get = Mock()
        with app.test_request_context("/foo"):
            resource.get.return_value = make_response('')
            resource.dispatch_request()

    def test_resource_error(self):
        app = Flask(__name__)
        resource = Resource()
        with app.test_request_context("/foo"):
            with pytest.raises(AssertionError):
                resource.dispatch_request()

    def test_resource_head(self):
        app = Flask(__name__)
        resource = Resource()
        with app.test_request_context("/foo", method="HEAD"):
            with pytest.raises(AssertionError):
                resource.dispatch_request()

    def test_fr_405(self):
        app = Flask(__name__)
        api = Api(app)
        api.add_resource(Foo, '/ids/<int:id>', endpoint="hello")
        app = app.test_client()
        resp = app.post('/ids/3')
        assert resp.status_code == 405
        expected_methods = ['HEAD', 'OPTIONS'] + Foo.methods
        assert resp.headers.get_all('Allow').sort() == expected_methods.sort()


class TestJSON(object):

    # def test_will_prettyprint_json_in_debug_mode(self):
    #     app = Flask(__name__)
    #     app.config['DEBUG'] = True
    #     api = Api(app)
    #     api.add_resource(Foo, '/foo', endpoint='bar')
    #
    #     with app.test_client() as client:
    #         rv = client.get('/foo')
    #
    #         # Python's dictionaries have random order (as of "new" Pythons,
    #         # anyway), so we can't verify the actual output here.  We just
    #         # assert that they're properly prettyprinted.
    #         lines = rv.data.splitlines()
    #         lines = [line.decode() for line in lines]
    #         assert lines[0] == "{"
    #         assert lines[1].startswith('    ') is True
    #         assert lines[3] == "}"
    #
    #         # Assert our trailing newline.
    #         assert rv.data.endswith(b'\n') is True

    def test_will_pass_options_to_json(self):

        app = Flask(__name__)
        api = Api(app, response=JSONResponse(indent=123))
        api.add_resource(Foo, '/foo', endpoint='bar')

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
        """What do I expect the datetime.datetime to be? rfc822, iso?
        """
        assert False
