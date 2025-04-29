# shell.nix
# Defines the development/runtime environment using Nix package manager.
{ pkgs ? import <nixpkgs> { } }:

pkgs.mkShell {
  # List of packages to make available in the environment.
  buildInputs = [
    pkgs.python3 # Python 3 interpreter
    pkgs.chromedriver # WebDriver for Chrome
    pkgs.uv # The uv Python package manager
    pkgs.chromium # Chromium browser
    pkgs.xorg.xauth # X11 authentication for GUI applications
    pkgs.xorg.xvfb # X virtual framebuffer for running GUI applications in headless mode
    pkgs.scrot # Screenshot utility
    # Add any other system-level dependencies required by your application here.
    # For example, if you need libraries for image processing: pkgs.libjpeg
  ];

  # Optional: Set environment variables if needed
  shellHook = ''
    export HEADLESS=True
    export DISPLAY=:0
    export XVFB=True
  '';
}
