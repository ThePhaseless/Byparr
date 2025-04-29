# flake.nix
# Defines the project structure, dependencies, and outputs using Nix Flakes.
{
  description =
    "A development environment and package set with Python, Chromedriver, and UV";

  # Define the inputs for the flake, primarily nixpkgs.
  inputs = {
    nixpkgs.url =
      "github:NixOS/nixpkgs/nixos-unstable"; # Or specify a specific release
  };

  # Define the outputs provided by the flake.
  outputs = { self, nixpkgs }:
    let
      # Define supported systems (adjust if needed for different architectures)
      supportedSystems =
        [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];

      # Helper function to generate outputs for each system
      forEachSupportedSystem = f:
        nixpkgs.lib.genAttrs supportedSystems (system:
          f {
            pkgs = import nixpkgs {
              inherit system;
              # overlays = []; # Add overlays if needed
            };
          });

      # Define the common set of packages needed
      commonPackages = pkgs: [
        pkgs.python3 # Python 3 interpreter
        pkgs.chromedriver # WebDriver for Chrome
        pkgs.chromium # Chromium browser
        pkgs.uv # The uv Python package manager
        pkgs.xorg.xvfb
        # Add any other system-level dependencies here that should be part of the final environment
      ];

    in {
      # Define the development shell environment(s).
      devShells = forEachSupportedSystem ({ pkgs }: {
        default = pkgs.mkShell {
          # Use the common package set for the shell
          packages = commonPackages pkgs;

          # Optional: Set environment variables if needed
          # shellHook = ''
          #   export MY_ENV_VAR="some_value"
          #   echo "Entered Nix development shell."
          # '';
        };
      });

      # Define packages output. This makes the dependencies installable via `nix profile install`.
      # We create a simple derivation that includes the necessary tools.
      packages = forEachSupportedSystem ({ pkgs }: {
        default = pkgs.buildEnv {
          name = "app-env";
          paths = commonPackages pkgs; # Include the common packages
          # If your app itself was a package, you'd include it here too.
          # pathsToLink = [ "/bin" ]; # Optional: specify paths to link into the profile
        };
      });

      # Optional: Define checks
      # checks = forEachSupportedSystem ({ pkgs }: {
      #   # Example check
      #   myCheck = pkgs.runCommand "my-check" {} ''
      #     echo "Running checks..."
      #     touch $out
      #   '';
      # });
    };
}
