#!/usr/bin/env python
from setuptools import setup, find_packages

setup(name='django-oscar-fees',
      version='0.1',
      url='https://github.com/JorrandeWit/django-oscar-fees',
      author="Jorran de Wit",
      author_email="jorrandewit@outlook.com",
      description="Apply fees to baskets and orders in django-oscar",
      classifiers=['Development Status :: 3 - Alpha',
                   'Environment :: Web Environment',
                   'Framework :: Django :: 1.9',
                   'Framework :: Django :: 1.10',
                   'Framework :: Django :: 1.11',
                   'Intended Audience :: Developers',
                   'License :: OSI Approved :: BSD License',
                   'Operating System :: OS Independent',
                   'Programming Language :: Python :: 3',
                   'Programming Language :: Python :: 3.2',
                   'Programming Language :: Python :: 3.3',
                   'Programming Language :: Python :: 3.4',
                   'Programming Language :: Python :: 3.5',
                   'Programming Language :: Python :: 3.6'],
      keywords=[
        'ecommerce',
        'oscar'
      ],
      license='BSD',
      packages=find_packages())
