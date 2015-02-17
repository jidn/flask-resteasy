#!/usr/bin/env python

from setuptools import setup, find_packages
from flask_resteasy import __version__

requirements = [
    'Flask>=0.10',
]

setup(
    name='Flask-RESTeasy',
    author='Clinton James',
    author_email='clinton.james@anuit.com',
    url='https://www.github.com/jidn/flask-restful/',
    download_url='https://github.com/jidn/flask-resteasy/tarball/0.0.1.dev',
    description='Create easy REST APIs with Flask',
    long_description=open('README.md').read(),
    version=__version__,
    keywords=['flask', 'REST'],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Framework :: Flask',
        'Intended Audience :: Developers',
        'Environment :: Web Environment',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 2.7',
        # 'Programming Language :: Python :: 3',
    ],
    py_modules=['flask_resteasy'],
    # packages=find_packages(exclude=['tests']),
    zip_safe=False,
    include_package_data=True,
    install_requires=requirements,
    # Install these with "pip install -e '.[paging]'" or '.[docs]'
    # extras_require={
    #     'docs': 'sphinx',
    # }
)
