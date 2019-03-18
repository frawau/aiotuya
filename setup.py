#!/usr/bin/env python3
# -*- coding:utf-8 -*-
import setuptools
version = "0.1.0b2"

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(name='aiotuya',
    packages=['aiotuya'],
    version=version,
    author='François Wautier, Max Isom et al.',
    author_email='francois@wautier.eu',
    description='Pure Python library to control/provision Tuya devices',
    long_description=long_description,
    url='https://github.com/frawau/aiotuya',
    platforms=['unix', 'linux', 'osx'],
    license='MIT',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: MIT LicenseO',
        'Operating System :: POSIX',
        'Operating System :: POSIX :: Linux',
        'Operating System :: MacOS :: MacOS X',
        'Topic :: Software Development :: Libraries',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: Implementation :: CPython'
    ],
    keywords=[
        'Tuya', 'IoT', 'WiFi', 'Home Automation',  'asyncio',
    ],
    install_requires=[
        'colorsys'
    ],
    entry_points={
        'console_scripts': [
            'aiotuya=aiotuya.__main__:main'
        ],
    },
    zip_safe=False
    )
