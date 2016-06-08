#!/usr/bin/env python
import os, sys
from setuptools import setup, find_packages

PYVER = sys.version_info[:2]  # (3, 4)
BASEDIR = os.path.dirname(__file__)

# Get version without import and fresh install race condition.
for _ in open(os.path.join(BASEDIR, 'flask_resteasy.py')).readlines():
    if _.startswith('__version__'):
        exec(_.strip(), None)
        break

requirements = [
    'Flask>=0.10',
]

setup(
    name='Flask-RESTeasy',
    author='Clinton James',
    author_email='clinton.james@anuit.com',
    url='https://www.github.com/jidn/flask-resteasy/',
    download_url='https://github.com/jidn/flask-resteasy/tarball/'+__version__,
    description='Create easy REST APIs with Flask',
    license='Apache License 2.0',
    long_description=open(os.path.join(BASEDIR, 'README.md')).read(),
    version=__version__,
    keywords=['flask', 'REST', 'json', 'MethodView'],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Framework :: Flask',
        'Intended Audience :: Developers',
        'Environment :: Web Environment',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ],
    py_modules=['flask_resteasy'],
    # packages=find_packages(exclude=['tests']),
    zip_safe=False,
    include_package_data=True,
    install_requires=requirements,
)
