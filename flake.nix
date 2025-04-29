{
  description = "flask-example";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/release-22.11";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let pkgs = import nixpkgs { inherit system; };
      in with pkgs; rec {
        # Development environment
        devShell = mkShell {
          name = "flask-example";
          nativeBuildInputs = [ uv ];
        };

        # Runtime package
        packages.app = poetry2nix.mkPoetryApplication { projectDir = ./.; };

        # The default package when a specific package name isn't specified.
        defaultPackage = packages.app;
      });
}
