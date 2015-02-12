from functools import wraps
try:
    from mock import Mock
except:
    # python3
    from unittest.mock import Mock
import pytest
import warnings
import flask
from flask import Flask, Blueprint, request
from flask.json import loads
import flask_resteasy

def to_json(v):
    return loads(v.data)

# Add a dummy Resource to verify that the app is properly set.
class HelloWorld(flask_resteasy.Resource):
    def get(self):
        return {}


class GoodbyeWorld(flask_resteasy.Resource):
    def __init__(self, err):
        self.err = err

    def get(self):
        flask.abort(self.err)

class TestAPIWithBlueprint(object):

    def test_api_base(self):
        blueprint = Blueprint('test', __name__)
        api = flask_resteasy.Api(blueprint)
        app = Flask(__name__)
        app.register_blueprint(blueprint)
        assert api.prefix == ''

    def test_api_delayed_initialization(self):
        blueprint = Blueprint('test', __name__)
        api = flask_resteasy.Api()
        api.init_app(blueprint)
        app = Flask(__name__)
        app.register_blueprint(blueprint)
        api.add_resource(HelloWorld, '/', endpoint="hello")

    def test_with_prefix(self):
        app = Flask(__name__)
        bp  = Blueprint('test', __name__, url_prefix='/bp')
        api = flask_resteasy.Api(prefix='/api')
        api.init_app(bp)

        api.add_resource(HelloWorld, '/hi')
        app.register_blueprint(bp)

        assert api.prefix == '/api'
        with app.test_client() as c:
            assert to_json(c.get('/bp/api/hi')) == {}

    def test_add_resource_endpoint(self):
        blueprint = Blueprint('test', __name__)
        api = flask_resteasy.Api(blueprint)
        view = Mock(**{'as_view.return_value': Mock(__name__='test_view')})
        api.add_resource(view, '/foo', endpoint='bar')
        app = Flask(__name__)
        app.register_blueprint(blueprint)
        view.as_view.assert_called_with('bar')

    def test_add_resource_endpoint_after_registration(self):
        blueprint = Blueprint('test', __name__)
        api = flask_resteasy.Api(blueprint)
        app = Flask(__name__)
        app.register_blueprint(blueprint)
        view = Mock(**{'as_view.return_value': Mock(__name__='test_view')})
        api.add_resource(view, '/foo', endpoint='bar')
        view.as_view.assert_called_with('bar')

    def test_url_with_api_prefix(self):
        blueprint = Blueprint('test', __name__)
        api = flask_resteasy.Api(blueprint, prefix='/api')
        api.add_resource(HelloWorld, '/hi', endpoint='hello')
        app = Flask(__name__)
        app.register_blueprint(blueprint, url_prefix='/bp')
        with app.test_request_context('/bp/api/hi'):
            assert request.endpoint == 'test.hello'
            assert flask.url_for('.hello') == '/bp/api/hi'

    def test_url_with_blueprint_prefix(self):
        blueprint = Blueprint('test', __name__, url_prefix='/bp')
        api = flask_resteasy.Api(blueprint)
        api.add_resource(HelloWorld, '/hi', endpoint='hello')
        app = Flask(__name__)
        app.register_blueprint(blueprint)
        with app.test_request_context('/bp/hi'):
            assert request.endpoint == 'test.hello'

    def test_url_with_registration_prefix(self):
        blueprint = Blueprint('test', __name__, url_prefix='/v')
        api = flask_resteasy.Api(blueprint, prefix='1.0')
        api.add_resource(HelloWorld, '/hi', endpoint='hello')
        app = Flask(__name__)
        app.register_blueprint(blueprint)
        with app.test_request_context('/v1.0/hi'):
            assert request.endpoint == 'test.hello'

    def test_registration_prefix_overrides_blueprint_prefix(self):
        blueprint = Blueprint('test', __name__, url_prefix='/bp')
        api = flask_resteasy.Api(blueprint, prefix='/api')
        api.add_resource(HelloWorld, '/hi', endpoint='hello')
        app = Flask(__name__)
        app.register_blueprint(blueprint, url_prefix='/reg')
        with app.test_request_context('/reg/api/hi'):
            assert request.endpoint == 'test.hello'

    def test_add_resource_kwargs(self):
        bp = flask.Blueprint('bp', __name__)
        api = flask_resteasy.Api(bp)
        @api.resource('/foo', defaults={'foo': 'bar'})
        class Foo(flask_resteasy.Resource):
            def get(self, foo):
                return foo
        app = flask.Flask(__name__)
        app.register_blueprint(bp)
        with app.test_client() as c:
            assert c.get('/foo').data == '"bar"'

    def test_resource_return_values(self):
        app = flask.Flask(__name__)
        app.config['DEBUG'] = True
        api = flask_resteasy.Api(app)
        @api.resource('/api/<int:k>')
        class Foo(flask_resteasy.Resource):
            def get(self, k):
                if k == 0:
                    return {}, 302, {'X-Junk': 'junk header'}
                elif k == 1:
                    return api.make_response(({'msg': 'no way'}, 403))

        with app.test_client() as c:
            rv = c.get('/api/0')
            assert rv.status_code == 302
            assert rv.data == '{}'
            assert rv.headers['X-junk'] == 'junk header'

            rv = c.get('/api/1')
            assert rv.status_code == 403
            data = loads(rv.data)
            assert data == {'msg': 'no way'}

            if app.debug == False:
                # if app.config['DEBUG'] = True you get
                # ValueError('View function did not return a response')
                rv = c.get('/api/2')
                assert rv.status_code == 500
                assert rv.headers['Content-Type'] == 'text/html'
            else:
                warnings.warn("skipping tests as flask app is DEBUG")

    def test_resource_exception_response(self):
        app = flask.Flask(__name__)
        app.config['DEBUG'] = True
        @app.errorhandler(ValueError)
        def value_error(err):
            return api.make_response(({'err': err.message}, 500))

        api = flask_resteasy.Api(app)
        @api.resource('/api')
        class Foo(flask_resteasy.Resource):
            def get(self):
                return None

        with app.test_client() as c:
            rv = c.get('/api')
            assert rv.status_code == 500
            data = loads(rv.data)
            assert data['err'].endswith('not return a response')


#     def test_url_part_order_aeb(self):
#         blueprint = Blueprint('test', __name__, url_prefix='/bp')
#         api = flask_resteasy.Api(blueprint, prefix='/api', url_part_order='aeb')
#         api.add_resource(HelloWorld, '/hi', endpoint='hello')
#         app = Flask(__name__)
#         app.register_blueprint(blueprint)
#         with app.test_request_context('/api/hi/bp'):
#             assert request.endpoint == 'test.hello'
#
#     def test_error_routing(self):
#         blueprint = Blueprint('test', __name__)
#         api = flask_resteasy.Api(blueprint)
#         api.add_resource(HelloWorld(), '/hi', endpoint="hello")
#         api.add_resource(GoodbyeWorld(404), '/bye', endpoint="bye")
#         app = Flask(__name__)
#         app.register_blueprint(blueprint)
#         with app.test_request_context('/hi', method='POST'):
#             assert api._should_use_fr_error_handler() is True
#             assert api._has_fr_route() is True
#         with app.test_request_context('/bye'):
#             api._should_use_fr_error_handler = Mock(return_value=False)
#             assert api._has_fr_route() is True
#
#     def test_non_blueprint_rest_error_routing(self):
#         blueprint = Blueprint('test', __name__)
#         api = flask_resteasy.Api(blueprint)
#         api.add_resource(HelloWorld(), '/hi', endpoint="hello")
#         api.add_resource(GoodbyeWorld(404), '/bye', endpoint="bye")
#         app = Flask(__name__)
#         app.register_blueprint(blueprint, url_prefix='/blueprint')
#         api2 = flask_resteasy.Api(app)
#         api2.add_resource(HelloWorld(), '/hi', endpoint="hello")
#         api2.add_resource(GoodbyeWorld(404), '/bye', endpoint="bye")
#         with app.test_request_context('/hi', method='POST'):
#             assert api._should_use_fr_error_handler() is False
#             assert api2._should_use_fr_error_handler() is True
#             assert api._has_fr_route() is False
#             assert api2._has_fr_route() is True
#         with app.test_request_context('/blueprint/hi', method='POST'):
#             assert api._should_use_fr_error_handler() is True
#             assert api2._should_use_fr_error_handler() is False
#             assert api._has_fr_route() is True
#             assert api2._has_fr_route() is False
#         api._should_use_fr_error_handler = Mock(return_value=False)
#         api2._should_use_fr_error_handler = Mock(return_value=False)
#         with app.test_request_context('/bye'):
#             assert api._has_fr_route() is False
#             assert api2._has_fr_route() is True
#         with app.test_request_context('/blueprint/bye'):
#             assert api._has_fr_route() is True
#             assert api2._has_fr_route() is False
#
#     def test_non_blueprint_non_rest_error_routing(self):
#         blueprint = Blueprint('test', __name__)
#         api = flask_resteasy.Api(blueprint)
#         api.add_resource(HelloWorld(), '/hi', endpoint="hello")
#         api.add_resource(GoodbyeWorld(404), '/bye', endpoint="bye")
#         app = Flask(__name__)
#         app.register_blueprint(blueprint, url_prefix='/blueprint')
#
#         @app.route('/hi')
#         def hi():
#             return 'hi'
#
#         @app.route('/bye')
#         def bye():
#             flask.abort(404)
#         with app.test_request_context('/hi', method='POST'):
#             assert api._should_use_fr_error_handler() is False
#             assert api._has_fr_route() is False
#         with app.test_request_context('/blueprint/hi', method='POST'):
#             assert api._should_use_fr_error_handler() is True
#             assert api._has_fr_route() is True
#         api._should_use_fr_error_handler = Mock(return_value=False)
#         with app.test_request_context('/bye'):
#             assert api._has_fr_route() is False
#         with app.test_request_context('/blueprint/bye'):
#             assert api._has_fr_route() is True
