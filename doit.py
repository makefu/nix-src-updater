""" usage: update-version [options] EXPR [VERSION [HASH]]

Options:
    -I P            explicitly set NIX_PATH to P
    --try-build     try to build the new derivation

If no VERSION is given, the script will try to find the latest release

"""
from nix import eval
from docopt import docopt
import logging as log
from os import environ
from os.path import expanduser
from pkg_resources import parse_version as parse_version
from pkg_resources import SetuptoolsVersion as Version
import sys
import re
import requests
#log.basicConfig(level=log.INFO)
log.basicConfig(level=log.DEBUG)

def fetchUrl(url):
    from subprocess import check_output,DEVNULL
    log.info(f"Fetching {url}")
    return check_output(["nix-prefetch-url", url],
            stderr=DEVNULL).decode().strip()

def githubTags(url):
    # github archive, TODO releases

    match = re.search("//github.com/(?P<owner>[^/]+)/(?P<repo>.+)\.git$",url) or \
            re.search("//github.com/(?P<owner>\w+)/(?P<repo>\w+)/archive/(?P<version>.*)\.(?P<extension>zip|tar\..*)$",url)
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
        tags = requests.get(f"https://pypi.python.org/pypi/{name}/json").json()['releases']
        return [parse_version(tag) for tag in tags.keys() if (type(parse_version(tag)) == Version)]



def guessNewVersion(name,current_version,urls):
    # TODO: try more than the first url
    url = urls[0]
    
    possibleServices = [ githubTags, pypiRelease]
    for srv in possibleServices:
        try:
            versions = srv(url)
        except Exception as e:
            log.info(f"Exception while querying versions via {srv} with {url}")
            log.error(e)
            continue

        if versions:
            log.debug(f"found versions: {[str(version) for version in versions]}")
            new_version = max(versions)
            if new_version > current_version:
                return new_version
            else:
                raise Exception(f"Current version {current_version} >= new {new_version}")
                

    # 'mirror://pypi/r/ropper/ropper-1.10.10.tar.gz'


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

    log.info(f"This system: {system}")
    log.info(f"NIX_PATH: {nix_path}")
    try:
        nv = neval(f"builtins.parseDrvName {expr}.name")
        name,version = nv['name'],parse_version(nv['version'])
        loc = neval(f"{expr}.meta.position").split(":")[0]
        log.info(f"File for {name}-{version} is {loc}")
        hash_algo = neval(f"{expr}.src.drvAttrs.outputHashAlgo")
        hash = neval(f"{expr}.src.drvAttrs.outputHash")
        # TODO: resolve mirrors
        try:
            urls = neval(f"{expr}.src.drvAttrs.urls")
        except:
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
            new_version = guessNewVersion(name,version,urls)
        except Exception as e:
            log.error(e)
            sys.exit(1)
        log.info(f"Found newer version for {name}: {new_version} (> {version})")
    # fetchedHash = fetchUrl(urls[0])

if __name__ == "__main__":
    main()
