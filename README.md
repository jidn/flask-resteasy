[![Build Status](https://travis-ci.org/jidn/flask-resteasy.svg?branch=master)](https://travis-ci.org/jidn/flask-resteasy.svg?branch=masterp)
[![Coverage Status](http://img.shields.io/coveralls/jidn/flask-resteasy/master.svg)](https://coveralls.io/r/jidn/flask-resteasy)

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
```
pip install flask_resteasy
```

# QuickStart
```
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
