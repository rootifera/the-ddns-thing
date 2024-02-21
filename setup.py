from setuptools import setup, find_packages

setup(
    name='the-ddns-thing',
    version='0.1.0',
    author='Omur Ozbahceliler',
    author_email='omur@rootifera.org',
    description='A dynamic DNS update tool.',
    long_description=open('README.md').read(),
    url='https://github.com/rootifera/the-ddns-thing',
    packages=find_packages(),
    install_requires=open('requirements.txt').read().splitlines(),
    classifiers=[
        'Programming Language :: Python :: 3',
        'Operating System :: POSIX :: Linux ',
    ],
    entry_points={
        'console_scripts': [
            'the-ddns-thing=the_ddns_thing.main:main',
        ],
    },
)
