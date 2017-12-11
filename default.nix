with import <nixpkgs> {};

with pkgs.python3Packages; buildPythonPackage { name = "updater-env";

  propagatedBuildInputs = [
    ((import ./pythonix) { inherit pkgs;})
    pkgs.nix
    docopt
    requests
  ];

src = ./.; }
