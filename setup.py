from setuptools import setup, find_packages

with open('requirements.txt') as f:
    requirements = f.read().splitlines()

setup(
    name='cloudflare-ddns-thing',
    version='0.1.0',
    description='A tool to update Cloudflare DNS records dynamically.',
    author='Omur Ozbahceliler',
    packages=find_packages(),
    install_requires=requirements,
    entry_points={
        'console_scripts': [
            'cloudflare-ddns-thing=src.main:main',
        ],
    },
    python_requires='>=3.10',
)
