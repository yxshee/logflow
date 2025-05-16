from setuptools import setup

setup(
    name='syslog-monitor',
    version='0.1.0',
    description='Cross-platform system performance monitoring GUI',
    author='Your Name',
    author_email='you@example.com',
    py_modules=['app'],
    install_requires=[
        'psutil>=5.9.0'
    ],
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Operating System :: OS Independent',
    ],
)
