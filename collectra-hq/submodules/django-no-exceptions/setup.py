#!/usr/bin/env python
from __future__ import absolute_import
from __future__ import unicode_literals
from setuptools import setup, find_packages

setup(
    name='django-no-exceptions',
    version='1.0.0',
    install_requires=[
        'django',
    ],
    packages=find_packages(exclude=['*.pyc']),
)
