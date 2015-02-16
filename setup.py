#!/usr/bin/env python

from setuptools import setup, find_packages
import sys
from flask_resteasy import __version__

requirements = [
    'Flask>=0.10',
]

setup(
    name='Flask-RESTeasy',
    version=__version__,
    url='https://www.github.com/jidn/flask-restful/',
    author='Clinton James',
    author_email='clinton.james@anuit.com',
    description='Create easy REST APIs with Flask',
    packages=find_packages(exclude=['tests']),
    zip_safe=False,
    include_package_data=True,
    platforms='any',
    install_requires=requirements,
    # Install these with "pip install -e '.[paging]'" or '.[docs]'
    # extras_require={
    #     'docs': 'sphinx',
    # }
)
