#!/usr/bin/env python3.6
""" usage: update-version [options] EXPR [VERSION [HASH]]

Options:
    -I P            explicitly set NIX_PATH to P
    --try-build     try to build the new derivation
    --lol LOL       set the log level [Default: INFO]
    --force         force the rehashing even if the version number is lower
    --no-build      do not try to build the expression at the end

If no VERSION is given, the script will try to find the latest release

Caveats:
    Currently only works with packages which have a meta subsection in the same file as the source.
    If the src rev or version is not derived from the derivation version the script will do nothing, however you can change the rev manually and rerun with --force

"""
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

@contextmanager
def allowAllEvaluations():
    with tempfile.NamedTemporaryFile() as cfg:
        cfg.write(b"pkgs: { allowUnfree = true; allowBroken = true; }")
        cfg.flush()
        environ['NIXPKGS_CONFIG'] = cfg.name
        yield

def setLOL(lol):
  numeric_level = getattr(logging,lol.upper(),None)
  if not isinstance(numeric_level,int):
    raise AttributeError('No such log level {}'.format(lol))
  logging.basicConfig(level=numeric_level)
  log.setLevel(numeric_level)


def replaceLast(loc,end_line,old,new,matcher):
    last_line = None

    with open(loc,"r") as srcfile:
        # python-packages:

        for num,line in enumerate(srcfile):
            if matcher.search(line):
                last_line = num +1 # enumerate counts from 0
                log.debug(f"Possible match at {num}: {line.strip()}")
            if num == end_line:
                log.debug("finished search")
                break

    if not last_line:
        raise Exception(f"Unable to find the {matcher} line of {old} -> {new}")

    for line in fileinput.input(loc,inplace=True):
        if fileinput.filelineno() == last_line:
            log.info(f"replacing {old} with {new} on line {last_line}")
            log.debug(f"old line: {line.strip()}")
            line = line.replace(str(old),str(new))
            log.debug(f"new line: {line.strip()}")
        sys.stdout.write(line)
    return True

def buildExpression(expr):
    log.info(f"Building {expr}")
    # TODO: we always want to see the build, right? If not:
    ## out = None if (log.getEffectiveLevel() == logging.DEBUG) else DEVNULL
    return check_output(f"nix-build -A {expr} <nixpkgs>".split(),
            stderr=None).decode().strip()

def fetchGit(attrs):
    """ takes the dict of drvAttrs as input """

    call = [ "nix-prefetch-git",attrs["url"],"--rev",attrs["rev"] ]
    from pprint import pprint
    if attrs["deepClone"]: call.append("--deepClone")
    if attrs["leaveDotGit"]: call.append("--leave-dotGit")
    if attrs["fetchSubmodules"]: call.append("--fetch-submodules")
    log.info(f"Fetching git as {call}")

    out = None if (log.getEffectiveLevel() == logging.DEBUG) else DEVNULL
    return json.loads(check_output(call,
        stderr=DEVNULL).decode())["sha256"]

def fetchUrl(attrs):
    url = attrs['urls'][0]
    call = ["nix-prefetch-url", url]
    log.info(f"Fetching {url}")

    # TODO: we assume that if postFetch is set then the package will be unpacked
    if attrs["postFetch"]:
        log.debug(f"Unpacking {url}")
        call.append("--unpack")

    out = None if (log.getEffectiveLevel() == logging.DEBUG) else DEVNULL
    log.debug(f"{call} - {out}")
    return check_output(call,stderr=out).decode().strip()

def githubTags(url):
    # github archive, TODO releases

    match = re.search("//github.com/(?P<owner>[^/]+)/(?P<repo>.+)\.git$",url) or \
            re.search("//github.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/archive/(?P<version>.*)\.(?P<extension>zip|tar\..*)$",url)
    if match:
        log.debug(match)
        owner = match.group('owner')
        repo = match.group('repo')
        tags = requests.get(f"https://api.github.com/repos/{owner}/{repo}/tags").json()
        # we only choose 'modern' tags, to avoid legacy shit
        return [parse_version(tag['name']) for tag in tags if (type(parse_version(tag['name'])) == Version)]

def pypiRelease(url):
    # TODO: direct ref to pypi?
    match = re.search("mirror://pypi/\w/(?P<name>[^/]+)/(?P=name)-(?P<version>.*)\.tar\.gz$",url)
    if match:
        log.debug(match)
        name = match.group('name')
        version = match.group('version')
        v = requests.get(f"https://pypi.python.org/pypi/{name}/json").json()['info']['version']
        # lets just return the latest version
        return [parse_version(v)]



def guessNewVersion(name,current_version,urls,force_rehash=False):
    # TODO: try more than the first url
    url = urls[0]

    possibleServices = [ githubTags, pypiRelease]
    for srv in possibleServices:
        log.debug(f"checking via {srv}")
        try:
            versions = srv(url)
        except Exception as e:
            log.info(f"Exception while querying versions via {srv} with {url}")
            log.error(e)
            continue

        if versions:
            log.debug(f"found versions: {[str(version) for version in versions]}")
            new_version = max(versions)
            if (new_version > current_version) or force_rehash:
                return new_version
            else:
                raise ValueError(f"Current version {current_version} >= new {new_version}")

    raise LookupError(f"Unable to find a valid version, please provide version manually")


def neval(expr):
    """ eval with nixpkgs loaded """
    return eval(f"with import <nixpkgs> {{}};{expr}")

def main():
    args = docopt(__doc__)
    system = eval("builtins.currentSystem")
    expr = args["EXPR"]
    nix_path = environ["NIX_PATH"] = expanduser(args["-I"] or environ["NIX_PATH"])
    new_version = args["VERSION"]
    new_hash = args["HASH"]
    force = args['--force']
    no_build = args['--no-build']

    setLOL(args['--lol'])

    log.info(f"This system: {system}")
    log.debug(f"NIX_PATH: {nix_path}")

    try:
        nv = neval(f"builtins.parseDrvName {expr}.name")
        name,version = nv['name'],parse_version(nv['version'].split('-')[-1])
        loc,locline = neval(f"{expr}.meta.position").split(":")
        locline = int(locline)
        log.info(f"File for {name}-{version} is {loc}:{locline}")
        hash_algo = neval(f"{expr}.src.drvAttrs.outputHashAlgo")
        hash = neval(f"{expr}.src.drvAttrs.outputHash")

        is_git = neval(f"builtins.hasAttr ''rev'' {expr}.src.drvAttrs")
        # TODO: resolve mirrors
        if not is_git:
            urls = neval(f"{expr}.src.drvAttrs.urls")
        else:
            log.debug("Using url instead of urls in drvAttrs")
            urls = [ neval(f"{expr}.src.drvAttrs.url") ]
        log.info(f"for urls {urls}")
        log.info(f"Hash {hash_algo} with {hash}")
        # log.info(f"new hash for input: {fetchedHash}")
    except Exception as e:
        log.error(f"Unable to find expression {expr}")
        log.error(e)
        sys.exit(1)

    if not new_version:
        log.info(f"Trying to guess new version for {name}")
        try:
            new_version = guessNewVersion(name,version,urls,force)
        except Exception as e:
            log.error(e)
            sys.exit(1)
        log.info(f"Found newer version for {name}: {new_version} (> {version})")

    matcher = re.compile(f'(version|rev)\s*=\s*"{version}";\s*(#.*)?$')
    replaceLast(loc,locline,version,new_version,matcher)

    attrs = neval(f"{expr}.src.drvAttrs")
    if is_git:
        new_hash = fetchGit(attrs)
    else:
        new_hash = fetchUrl(attrs)

    log.info(f"new hash for {expr} is {new_hash}")

    # TODO: not sure if hash_algo always matches
    matcher = re.compile(f'({hash_algo})\s*=\s*"{hash}";$\s*(#.*)?')
    replaceLast(loc,locline,hash,new_hash,matcher)
    if not no_build:
        log.info(f"trying to build changed expression {expr}")
        try:
            buildExpression(expr)
        except CalledProcessError:
            log.error(f"Unable to build {expr}, go ahead and follow the white rabbit")
            sys.exit(1)
    else:
        log.info(f"Build of {expr} skipped")
    log.info("Finished")
    sys.exit(0)


def allowAllMain():
    with allowAllEvaluations():
        main()

if __name__ == "__main__":
    allowAllMain()
