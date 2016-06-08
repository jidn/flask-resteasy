[![build status](https://travis-ci.org/jidn/flask-resteasy.svg?branch=master)](https://travis-ci.org/jidn/flask-resteasy.svg?branch=masterp)
![version](http://img.shields.io/pypi/v/flask-resteasy.svg)
![license](http://img.shields.io/pypi/l/flask-resteasy.svg)
[![coverage](https://coveralls.io/repos/github/jidn/flask-resteasy/badge.svg?branch=master)](https://coveralls.io/github/jidn/flask-resteasy?branch=master)
![downloads](http://img.shields.io/pypi/dm/flask-resteasy.svg)

# Flask-RESTeasy

It starts with an itch.  I was using Flask-RESTful but I soon started
having to work around it with request parsing and output fields caused
errors.  I got frustrated.  I loved the project, but it was doing more
than what I wanted it to do.

I just wanted something to ease the setup and binding of flask MethodViews
for handling JSON REST APIs.  The rest can be handled by other packages
dedicated to their tasks.  I kept the basic resource handling for both
apps and blueprints and removed the rest: request parsing, output fields,
authentication, and static error handling.

I wanted something simple in the way Flask was simple.  This is my
attempt at making it so.  If you have seen Flask-RESTful, this will
look very familiar.

# Install

For install you can use pip:

```console
$ pip install flask_resteasy
```

# QuickStart
```python
from flask import Flask
from flask.ext import resteasy

app = Flask(__name__)
api = resteasy.Api(app)

@api.resource('/')
class HelloWorld(resteasy.Resource):
    def get(self):
        return {'msg': 'Hello world'}

    def delete(self):
        return {'msg': 'Sorry Dave.'}

if __name__ == '__main__':
    app.run(debug=True)
```

Execute that code and you have a running server on port 5000.  If you get an error, you probably have something else running on that port.  Either stop the other process or change the port in your Flask app.

Now either check with a browser, or use the following commands.

```console
$ curl http://localhost:5000
{"msg": "Hello world"}

$ curl http://localhost:5000 -X "DELETE"
{"msg": "Sorry Dave."}
```
