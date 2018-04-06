#!/usr/bin/env python3.6
""" usage: gen-expression [options] TYPE NAME

Options:
    -I P            explicitly set NIX_PATH to P
    --lol LOL       set the log level [Default: INFO]
    --force         force the rehashing even if the version number is lower
    --build=P       add extra build requirements (space delimited)
    --check=P       add extra check requirements (space delimited)
    --license=L     explicitly set the license
    --maintainer=M  set yourself as new maintainer
    --version=V     explicitly set the version you want

Supported types:
    pypi            python package index generic


"""
from nix_src_updater.cli import fetchUrl
import json
from nix import eval
import fileinput
import tempfile
from docopt import docopt
import logging
from os import environ
from os.path import expanduser
from pkg_resources import parse_version as parse_version
from pkg_resources import SetuptoolsVersion as Version
import sys
import re
import requests
from subprocess import check_output,DEVNULL,CalledProcessError
from contextlib import contextmanager

log = logging.getLogger('cli')

def setLOL(lol):
  numeric_level = getattr(logging,lol.upper(),None)
  if not isinstance(numeric_level,int):
    raise AttributeError('No such log level {}'.format(lol))
  logging.basicConfig(level=numeric_level)
  log.setLevel(numeric_level)


def neval(expr):
    """ eval with nixpkgs loaded """
    return eval(f"with import <nixpkgs> {{}};{expr}")

def getPypiInfo(name):
    return requests.get(f"https://pypi.python.org/pypi/{name}/json").json()['info']

def main():
    args = docopt(__doc__)
    name = args["NAME"]
    nix_path = environ["NIX_PATH"] = expanduser(args["-I"] or environ["NIX_PATH"])
    force = args['--force']
    typ = args['TYPE']
    extraBuild = args['--build'] or ""
    extraCheck = args['--check'] or ""
    maintainer = args['--maintainer'] or ""


    setLOL(args['--lol'])
    base_dir = eval("builtins.toString <nixpkgs>")
    log.info(base_dir)
    if typ.lower() == 'pypi':
        info = getPypiInfo(name)
        url = info["home_page"]
        license = args["--license"] or info["license"] or "PLACEHOLDER_LICENSE"
        version = args["--version"] or info["version"]
        # extra == tests
        build = [ req.split()[0].lower().replace('.','-').replace(';','') for req in info.get("requires_dist",[]) ] + extraBuild.split()
        check = extraCheck.split() if extraCheck else []

        description = info["summary"]
        hjoin = lambda lst: '\n, '.join(lst)
        njoin = lambda lst: '\n    '.join(lst)
        sha256 = fetchUrl({ "urls": [f"mirror://pypi/{name[0]}/{name}/{name}-{version}.tar.gz"],"postFetch":False})
        print(
f"""{{ lib, fetchPypi, buildPythonPackage
# buildInputs
, {hjoin(build)}
# checkInputs
, {hjoin(check)}
}}:

# {name} = callPackage ../development/python-modules/{name} {{}};
buildPythonPackage rec {{
  pname = "{name}";
  version = "{version}";

  src = fetchPypi {{
    inherit pname version;
    sha256 = "{sha256}";
  }};

  propagatedBuildInputs = [
    {njoin(build)}
  ];

  checkInputs = [
    {njoin(check)}
  ];

  meta = with lib; {{
    description = "{description}";
    homepage = "{url}";
    # TODO License
    license = licenses."{license}";
    maintainers = with maintainers; [ {maintainer} ];
  }};
}}""")

    else:
        log.error(f"unsupported type {typ}")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
