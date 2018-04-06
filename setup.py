import sys
from setuptools import setup
import nix_src_updater

setup(
    name='nix_src_updater',
    version=nix_src_updater.__version__,

    description='cli tool to update derivations in nix',
    long_description=open("README.md").read(),
    license='MIT',
    download_url='https://pypi.python.org/pypi/nix_src_updater/',

    author='makefu',
    author_email='pypi@syntax-fehler.de',
    install_requires = [ 'docopt', 'requests' ],
    packages=['nix_src_updater', 'nix_src_updater.gen_skeleton' ],
    entry_points={
        'console_scripts' : [
            'nix-src-updater = nix_src_updater.cli:allowAllMain',
            'nix-gen-skeleton = nix_src_updater.gen_skeleton.cli:main'
            ]
        },

    classifiers=[
        "Intended Audience :: Developers",
        "Natural Language :: English",
        "Operating System :: POSIX :: Linux",
        "Development Status :: 3 - Alpha",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: Implementation :: CPython",
    ],
)

