#!/usr/bin/env python
# -*- encoding: utf-8 -*-
__author__ = "Peter Bryant <p.misc2@rimuhosting.com>"
import os
from setuptools import setup
NAME = "RimuHostingAPI"
GITHUB_URL = "https://github.com/pbkwee/%s" % (NAME)
DESCRIPTION = "Python interface to RimuHosting API"

VERSION = "0.0.7"

#REQUIREMENTS = ['requests','objectpath','pytz', 'jsonpath_ng']
REQUIREMENTS = ['requests','jsonpath_ng']

setup(name=NAME,
              version=VERSION,
              download_url="%s/zipball/master" % GITHUB_URL,
              description=DESCRIPTION,
              install_requires=REQUIREMENTS,
              author='Peter Bryant',
              author_email='p.misc2@rimuhosting.com',
              url=GITHUB_URL,
              license='GPLv3+',
              py_modules=['rimuapi'],
      classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: System :: Distributed Computing',
        'Topic :: Utilities',
        ],
      )


