# updater for nix src

Tries to find the latest version of the derivation source and tries to fix the source file.

# Install

```
git clone https://github.com/Mic92/pythonix/ # TODO: pin to ref
nix-shell
python doit.py  python2Packages.cairosvg -I 'nixpkgs=~/nixpkgs'
```
