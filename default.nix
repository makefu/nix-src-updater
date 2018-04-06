with import <nixpkgs> {};

with pkgs.python3Packages; buildPythonPackage { name = "updater-env";

  propagatedBuildInputs = [
    pythonix
    pkgs.nix
    docopt
    requests
    pkgs.nix-prefetch-scripts
  ];

src = ./.; }
