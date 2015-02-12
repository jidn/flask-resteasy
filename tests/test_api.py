from flask import Flask, redirect, views
from flask.signals import got_request_exception, signals_available
try:
    from mock import Mock, patch
except:
    # python3
    from unittest.mock import Mock, patch
import flask
from flask.json import dumps, loads
import flask_resteasy
import pytest

def to_json(v):
    return loads(v.data)

# Add a dummy Resource to verify that the app is properly set.
resp_helloworld = {'hello':'World!'}
class HelloWorld(flask_resteasy.Resource):
    def get(self):
        return resp_helloworld


class TestAPI(object):

    def test_api(self):
        app = Mock()
        app.configure_mock(**{'record.side_effect': AttributeError})
        api = flask_resteasy.Api(app, prefix='/foo')
        assert api.prefix == '/foo'

    def test_api_delayed_initialization(self):
        app = Flask(__name__)
        api = flask_resteasy.Api()
        api.add_resource(HelloWorld, '/', endpoint="hello")
        api.init_app(app)
        assert HelloWorld.endpoint == 'hello'
        with app.test_client() as client:
            assert client.get('/').status_code == 200

    def test_resource_decorator(self):
        app = flask.Flask(__name__)
        api = flask_resteasy.Api(app)

        @api.resource('/api')
        class Foo(flask_resteasy.Resource):
            def get(self):
                return 'foo'

        with app.test_client() as c:
            c.get('/api').data == 'foo'

    def test_add_resouce_multi_url(self):
        app = flask.Flask(__name__)
        api = flask_resteasy.Api(app)

        api.add_resource(HelloWorld, '/api', '/api2')

        with app.test_client() as c:
            assert to_json(c.get('/api')) == resp_helloworld
            assert to_json(c.get('/api2')) == resp_helloworld


    def test_api_same_url(self):
        #TODO Should this pop an error?
        app = Flask(__name__)
        api = flask_resteasy.Api(app, prefix='/v1')
        @api.resource('/api')
        class Foo(flask_resteasy.Resource):
            def get(self):
                return 'foo'
        @api.resource('/api')
        class Bar(flask_resteasy.Resource):
            def get(self):
                return 'bar'

        with app.test_request_context('/api'):
            assert flask.url_for('foo') == flask.url_for('bar')
            assert flask.url_for('foo') == '/v1/api'
        with app.test_client() as c:
            rv = c.get('/v1/api')
            assert rv.data == '"foo"'

    def test_handle_api_error(self):
        api = flask_resteasy.Api()
        @api.resource('/api', endpoint='api')
        class Test(flask_resteasy.Resource):
            def get(self):
                flask.abort(404)

        app = Flask(__name__)
        api.init_app(app)

        @app.errorhandler(404)
        def not_found(err):
            rv = {'code': 404, 'msg': 'Not found'}
            return flask_resteasy.make_json_response(rv, 404)

        with app.test_client() as c:
            rv = c.get("/api")
            assert rv.status_code == 404
            assert rv.headers['Content-Type'] == 'application/json'
            data = loads(rv.data.decode())
            assert data.get('code') == 404
            assert 'msg' in data

    def test_handle_non_api_error(self):
        app = Flask(__name__)
        flask_resteasy.Api(app)

        with app.test_client() as c:
            rv = c.get("/foo")
            assert rv.status_code == 404
            assert rv.headers['Content-Type'] == 'text/html'

    def test_url_for(self):
        app = Flask(__name__)
        api = flask_resteasy.Api(app)
        api.add_resource(HelloWorld, '/greeting/<int:idx>')
        with app.test_request_context('/foo'):
            assert api.url_for(HelloWorld, idx=5) == '/greeting/5'

    def test_decorator(self):
        def return_zero(func):
            return 0

        app = Mock(flask.Flask)
        app.view_functions = {}
        view = Mock()
        api = flask_resteasy.Api(app)
        api.decorators.append(return_zero)
        api.output = Mock()
        api.add_resource(view, '/foo', endpoint='bar')

        app.add_url_rule.assert_called_with('/foo', view_func=0)

    def test_add_resource_endpoint(self):
        app = Mock()
        app.view_functions = {}
        view = Mock()

        api = flask_resteasy.Api(app)
        api.output = Mock()
        api.add_resource(view, '/foo', endpoint='bar')

        view.as_view.assert_called_with('bar')

    def test_add_two_conflicting_resources_on_same_endpoint(self):
        app = Flask(__name__)
        api = flask_resteasy.Api(app)

        class Foo1(flask_resteasy.Resource):
            def get(self):
                return 'foo1'

        class Foo2(flask_resteasy.Resource):
            def get(self):
                return 'foo2'

        api.add_resource(Foo1, '/foo', endpoint='bar')
        with pytest.raises(ValueError):
            api.add_resource(Foo2, '/foo/toto', endpoint='bar')

    def test_add_the_same_resource_on_different_endpoint(self):
        app = Flask(__name__)
        api = flask_resteasy.Api(app)
        app.config['DEBUG'] = True

        class Foo1(flask_resteasy.Resource):
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
        app = Mock(flask.Flask)
        app.view_functions = {}
        api = flask_resteasy.Api(app)
        api.output = Mock()
        api.add_resource(views.MethodView, '/foo')

        app.add_url_rule.assert_called_with('/foo', view_func=api.output())

    def test_resource_decorator(self):
        app = Mock(flask.Flask)
        app.view_functions = {}
        api = flask_resteasy.Api(app)
        api.output = Mock()

        @api.resource('/foo', endpoint='bar')
        class Foo(flask_resteasy.Resource):
            pass

        app.add_url_rule.assert_called_with('/foo', view_func=api.output())

    def test_add_resource_kwargs(self):
        app = flask.Flask(__name__)
        app.config['DEBUG'] = True
        api = flask_resteasy.Api(app)
        @api.resource('/foo', defaults={'foo': 'bar'})
        class Foo(flask_resteasy.Resource):
            def get(self, foo):
                return foo
        with app.test_client() as c:
            assert c.get('/foo').data == '"bar"'

    def test_output_unpack(self):
        def make_empty_response():
            return {'foo': 'bar'}

        app = Flask(__name__)
        api = flask_resteasy.Api(app)

        with app.test_request_context("/foo"):
            wrapper = api.output(make_empty_response)
            resp = wrapper()
            assert resp.status_code == 200
            assert resp.data.decode() == '{"foo": "bar"}'

    # def test_output_func(self):
    #
    #     def make_empty_resposne():
    #         return flask.make_response('')
    #
    #     app = Flask(__name__)
    #     api = flask_resteasy.Api(app)
    #
    #     with app.test_request_context("/foo"):
    #         wrapper = api.output(make_empty_resposne)
    #         resp = wrapper()
    #         assert resp.status_code == 200
    #         assert resp.data.decode() == ''
    #
    # def test_resource(self):
    #     app = Flask(__name__)
    #     resource = flask_resteasy.Resource()
    #     resource.get = Mock()
    #     with app.test_request_context("/foo"):
    #         resource.dispatch_request()
    #
    # def test_resource_resp(self):
    #     app = Flask(__name__)
    #     resource = flask_resteasy.Resource()
    #     resource.get = Mock()
    #     with app.test_request_context("/foo"):
    #         resource.get.return_value = flask.make_response('')
    #         resource.dispatch_request()
    #
    # def test_resource_text_plain(self):
    #     app = Flask(__name__)
    #
    #     def text(data, code, headers=None):
    #         # return flask.make_response(six.text_type(data))
    #         return flask.make_response(data)
    #
    #     class Foo(flask_resteasy.Resource):
    #
    #         representations = {
    #             'text/plain': text,
    #         }
    #
    #         def get(self):
    #             return 'hello'
    #
    #     with app.test_request_context("/foo", headers={'Accept': 'text/plain'}):
    #         resource = Foo()
    #         resp = resource.dispatch_request()
    #         assert resp.data.decode() == 'hello'
    #
    # def test_resource_error(self):
    #     app = Flask(__name__)
    #     resource = flask_resteasy.Resource()
    #     with app.test_request_context("/foo"):
    #         with pytest.raises(AssertionError):
    #             resource.dispatch_request()
    #
    # def test_resource_head(self):
    #     app = Flask(__name__)
    #     resource = flask_resteasy.Resource()
    #     with app.test_request_context("/foo", method="HEAD"):
    #         with pytest.raises(AssertionError):
    #             resource.dispatch_request()
    #
    # def test_abort_data(self):
    #     try:
    #         flask_resteasy.abort(404, foo='bar')
    #         assert False  # We should never get here
    #     except Exception as e:
    #         assert e.data == {'foo': 'bar'}
    #
    # def test_endpoints(self):
    #     app = Flask(__name__)
    #     api = flask_resteasy.Api(app)
    #     api.add_resource(HelloWorld, '/ids/<int:id>', endpoint="hello")
    #     with app.test_request_context('/foo'):
    #         assert api._has_fr_route() is False
    #
    #     with app.test_request_context('/ids/3'):
    #         assert api._has_fr_route() is True
    #
    # def test_url_for(self):
    #     app = Flask(__name__)
    #     api = flask_resteasy.Api(app)
    #     api.add_resource(HelloWorld, '/ids/<int:id>')
    #     with app.test_request_context('/foo'):
    #         assert api.url_for(HelloWorld, id=123) == '/ids/123'
    #
    # def test_fr_405(self):
    #     app = Flask(__name__)
    #     api = flask_resteasy.Api(app)
    #     api.add_resource(HelloWorld, '/ids/<int:id>', endpoint="hello")
    #     app = app.test_client()
    #     resp = app.post('/ids/3')
    #     assert resp.status_code == 405
    #     assert resp.content_type == api.default_mediatype
    #     expected_methods = ['HEAD', 'OPTIONS'] + HelloWorld.methods
    #     assert resp.headers.get_all('Allow').sort() == expected_methods.sort()
    #
    # def test_will_prettyprint_json_in_debug_mode(self):
    #     app = Flask(__name__)
    #     app.config['DEBUG'] = True
    #     api = flask_resteasy.Api(app)
    #
    #     class Foo1(flask_resteasy.Resource):
    #         def get(self):
    #             return {'foo': 'bar', 'baz': 'asdf'}
    #
    #     api.add_resource(Foo1, '/foo', endpoint='bar')
    #
    #     with app.test_client() as client:
    #         foo = client.get('/foo')
    #
    #         # Python's dictionaries have random order (as of "new" Pythons,
    #         # anyway), so we can't verify the actual output here.  We just
    #         # assert that they're properly prettyprinted.
    #         lines = foo.data.splitlines()
    #         lines = [line.decode() for line in lines]
    #         assert lines[0] == "{"
    #         assert lines[1].startswith('    ') is True
    #         assert lines[2].startswith('    ') is True
    #         assert lines[3] == "}"
    #
    #         # Assert our trailing newline.
    #         assert foo.data.endswith(b'\n') is True
    #
    # def test_will_pass_options_to_json(self):
    #
    #     app = Flask(__name__)
    #     api = flask_resteasy.Api(app)
    #
    #     class Foo1(flask_resteasy.Resource):
    #         def get(self):
    #             return {'foo': 'bar'}
    #
    #     api.add_resource(Foo1, '/foo', endpoint='bar')
    #
    #     # We patch the mediatype_handlers module here, with two things:
    #     #   1. Set the settings dict() with some value
    #     #   2. Patch the json.dumps function in the module with a Mock object.
    #
    #     from flask import json as json_rep
    #     json_dumps_mock = Mock(return_value='bar')
    #     new_settings = {'indent': 123}
    #
    #     with patch.multiple(json_rep, dumps=json_dumps_mock,
    #                         settings=new_settings):
    #         with app.test_client() as client:
    #             client.get('/foo')
    #
    #     # Assert that the function was called with the above settings.
    #     data, kwargs = json_dumps_mock.call_args
    #     assert json_dumps_mock.called
    #     assert kwargs['indent'] == 123
    #
    # def test_redirect(self):
    #     app = Flask(__name__)
    #     api = flask_resteasy.Api(app)
    #
    #     class FooResource(flask_resteasy.Resource):
    #         def get(self):
    #             return redirect('/')
    #
    #     api.add_resource(FooResource, '/api')
    #
    #     app = app.test_client()
    #     resp = app.get('/api')
    #     assert resp.status_code == 302
    #     assert resp.headers['Location'] == 'http://localhost/'
    #
    # def test_json_float_marshalled(self):
    #     app = Flask(__name__)
    #     api = flask_resteasy.Api(app)
    #
    #     class FooResource(flask_resteasy.Resource):
    #         fields = {'foo': flask_resteasy.fields.Float}
    #
    #         def get(self):
    #             return flask_resteasy.marshal({"foo": 3.0}, self.fields)
    #
    #     api.add_resource(FooResource, '/api')
    #
    #     app = app.test_client()
    #     resp = app.get('/api')
    #     assert resp.status_code == 200
    #     assert resp.data.decode('utf-8') == '{"foo": 3.0}'
    #
    # def test_custom_error_message(self):
    #     errors = {
    #         'FooError': {
    #             'message': "api is foobar",
    #             'status': 418,
    #         }
    #     }
    #
    #     class FooError(ValueError):
    #         pass
    #
    #     app = Flask(__name__)
    #     api = flask_resteasy.Api(app, errors=errors)
    #
    #     exception = FooError()
    #     exception.code = 400
    #     exception.data = {'message': 'FooError'}
    #
    #     with app.test_request_context("/foo"):
    #         resp = api.handle_error(exception)
    #         assert resp.status_code == 418
    #         data = loads(resp.data.decode('utf8'))
    #         assert data == {"message": "api is foobar", "status": 418}