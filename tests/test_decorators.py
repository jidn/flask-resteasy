import inspect
# try:
#     from mock import Mock, patch
# except:
#     # python3
#     from unittest.mock import Mock, patch
from functools import partial, wraps
from flask import Flask, Response

from flask_resteasy import Api, Resource, unpack


def add_header(header, value=None):
    """Add a header to the response.

    :param header: the header to add
    :type header: str
    :param value: the value to assign to the header, defaults to string representation of response
    :type value: str
    """
    def foo_header(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            rv = unpack(func(*args, **kwargs))
            if isinstance(rv, Response):
                rv.headers[header] = value or str(rv)
            else:
                data, code, headers = rv
                rv[-1][header] = value or str(data)
            return rv
        return wrapper
    return foo_header


def append_header(header, value):
    """Append to a header
    """
    def foo_header(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            rv = unpack(func(*args, **kwargs))
            if isinstance(rv, Response):
                rv.headers[header] = rv.headers.setdefault(header, '') + value
            else:
                rv[-1][header] = rv[-1].setdefault(header, '') + value
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
                    store.append((rv, from_frame(outer_frames[idx + 1])))
                    break
            return rv
        return wrapper
    return decorator


class TestDecorators(object):

    def test_decorator_heirachy(self):
        """
        api = Api(app, decorators=[F('api')])
        @api.add_resource('/foo', decorators=[F('add')])
        class Decorator(Resource):
            decorators = [F('resource')]

            @F('method')
            def get(self):
                return {}

        """
        AH = partial(append_header, 'x-trace')
        app = Flask(__name__)
        api = Api(app, decorators=[AH(' A1'), AH(' A2')])

        @api.resource('/api', decorators=[AH(' a1'), AH(' a2')])
        class Foo(Resource):
            decorators = [AH(' r1'), AH(' r2')]

            @append_header('x-trace', ' m1')
            @append_header('x-trace', 'm2')
            def get(self):
                return {}, 200, {}

        with app.test_client() as c:
            rv = c.get('/api')
            assert rv.status_code == 200
            assert rv.headers['X-TRACE'] == "m2 m1 r1 r2 a1 a2 A1 A2"

    def test_decorator_view_response_types(self):
        """
        api = Api(app, decorators=[decorator_1])
        class Decorator(Resource, decorators=[decorator_2]):
            decorators = [decorator_3]

            @decorator_4
            def get(self):
                return {}

        decorator1 gets :class:`Flask.Response`
        decorator2 gets :class:`Flask.Response`
        decorator3 gets return value from Resource method
        decorator4 gets return value from Resource method
        """
        app = Flask(__name__)
        app.config['DEBUG'] = True
        api = Api(app, decorators=[add_header('x-api')])

        @api.resource('/api', decorators=[add_header('x-add')])
        class Foo(Resource):
            decorators = [add_header('x-class')]

            @add_header('x-method')
            def get(self):
                return {}

        with app.test_client() as c:
            rv = c.get('/api')
            assert rv.status_code == 200
            assert rv.headers['X-API'].startswith("<Response")
            assert rv.headers['X-ADD'].startswith("<Response")
            assert rv.headers['X-CLASS'] == "{}"
            assert rv.headers['X-METHOD'] == "{}"
