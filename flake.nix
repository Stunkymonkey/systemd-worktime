{
  description = "Listing past uptimes of systemd";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
        pythonEnv = pkgs.python3.withPackages (ps: with ps; [
          systemd-python
        ]);
        systemd-worktime = pkgs.writeShellApplication {
          name = "systemd-worktime";
          runtimeInputs = [ pythonEnv ];
          text = ''
            python3 ${./systemd-worktime.py} "$@"
          '';
        };
      in
      {
        packages.default = systemd-worktime;

        apps.default = {
          type = "app";
          program = "${systemd-worktime}/bin/systemd-worktime";
        };

        checks = {
          ruff = pkgs.runCommand "ruff-check"
            {
              nativeBuildInputs = [ pkgs.ruff ];
            } ''
            ruff check ${./.}
            touch $out
          '';
        };

        devShells.default = pkgs.mkShell {
          buildInputs = [ pythonEnv ];
          nativeBuildInputs = [ pkgs.ruff ];
        };
      }
    );
}
