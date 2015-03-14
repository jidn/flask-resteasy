import os
import pytest
import logging
import inspect
from flask_resteasy import Resource

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__) #'flask-resteasy.test')
handler = logging.FileHandler('test.log')
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s %(name)s|%(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

def stack_names(starting=1, cnt=3):
    f = inspect.stack()
    return [(os.path.basename(x.filename), x.lineno, x.function) for x in
            [inspect.getframeinfo(_[0]) for _ in f[starting:starting + cnt]]]

def make_foo(starting=1):
    class Foo(Resource):
        resp = {'msg':'foo'}
        def get(self):
            return Foo.resp
    logger.debug('%s %s',
                 hasattr(Foo, 'endpoint'),
                 stack_names(starting))
    assert hasattr(Foo, 'endpoint') == False
    return Foo

