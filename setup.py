#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import sys
import re

from setuptools import setup, find_packages

version = re.search("__version__ = '([^']+)'",
                    open('weave/__init__.py').read()).group(1)

setup(
    name='weave-minimal',
    version=version,
    author='posativ',
    author_email='info@posativ.org',
    packages=find_packages(),
    zip_safe=True,
    url='https://github.com/posativ/weave-minimal/',
    license='BSD revised',
    description='lightweight firefox weave/sync server',
    classifiers=[
        "Development Status :: 4 - Beta",
        "Topic :: Internet",
        "Topic :: Internet :: WWW/HTTP :: HTTP Servers",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
        "License :: OSI Approved :: BSD License",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7"
    ],
    install_requires=['werkzeug'],
    entry_points={
        'console_scripts':
            ['weave-minimal = weave:main'],
    },
)
