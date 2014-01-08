#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from sys import version_info
from setuptools import setup, find_packages

if version_info < (3, 0):
    requires = ['werkzeug>=0.8']
    if version_info < (2, 7):
        requires += ["argparse"]
else:
    requires = ['werkzeug>=0.9']

setup(
    name='weave-minimal',
    version='1.5',
    author='Martin Zimmermann',
    author_email='info@posativ.org',
    packages=find_packages(),
    zip_safe=True,
    url='https://github.com/posativ/weave-minimal/',
    license='BSD revised',
    description='lightweight firefox weave/sync server',
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Topic :: Internet",
        "Topic :: Internet :: WWW/HTTP :: HTTP Servers",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
        "License :: OSI Approved :: BSD License",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.3"
    ],
    install_requires=requires,
    entry_points={
        'console_scripts':
            ['weave-minimal = weave:main'],
    },
)
