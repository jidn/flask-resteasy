import inspect
from functools import wraps
import flask
from flask_resteasy import Api, Resource, unpack

def add_header(header, value):
    def foo_header(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            rv = unpack(func(*args, **kwargs))
            if isinstance(rv, flask.Response):
                rv.headers[header] = rv
            else:
                data, code, headers = rv
                rv[-1][header] = data
            return rv
        return wrapper
    return foo_header

def return_values(store):
    """Pulls out what code called this decorator assuming all decorators
     in the chain use the name 'wrapper' as we do
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            rv = func(*args, **kwargs)
            def from_frame(fr):
                (frame, filename, line_number, function_name, lines, index) = fr
                return (line_number, function_name, filename, lines)
            outer_frames = inspect.getouterframes(inspect.currentframe())
            for idx, oframe in enumerate(outer_frames):
                if oframe[3] == 'wrapper':
                    store.append((rv, from_frame(outer_frames[idx+1])))
                    break
            return rv
        return wrapper
    return decorator


class TestDecorators(object):

    def test_decorators_all_levels(self):
        """
        api = Api(app, decorators=[decorator_1])
        class Decorator(Resource, decorators=[decorator_2]):
            decorators = [decorator_2]

            @decorator_3
            def get(self):
                return {}

        decorator1 gets :class:`Flask.Response`
        decorator2 gets return value from Resource method
        decorator3 gets return value from Resource method
        """
        app = flask.Flask(__name__)
        app.config['DEBUG'] = True
        api = Api(app, decorators=[add_header('x-api', 'api')])
        @api.resource('/api', decorators=[add_header('x-resource', 'resource')])
        class Mine(Resource):

            @add_header('x-method', 'method')
            def get(self):
                return {'msg': 'hi'}

        with app.test_client() as c:
            rv = c.get('/api')
            assert rv.status_code == 200
            assert rv.headers['X-API'].startswith("<Response")
            assert rv.headers['X-RESOURCE'].startswith("{'msg")
            assert rv.headers['X-METHOD'].startswith("{'msg")
