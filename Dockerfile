# Dockerfile
# Use an official Nix image as the base, ensuring flakes are enabled.
# The nixos/nix image usually has flakes enabled by default.
FROM nixos/nix:latest

# Set the working directory inside the container
WORKDIR /app

# Copy the flake definition and the lock file for reproducibility
COPY flake.nix flake.lock pyproject.toml uv.lock ./

# Copy your Python application script

# --- Optional: Install Python dependencies using uv within the flake environment ---
# If you have a requirements.txt (or pyproject.toml), uncomment and adapt.
# Copy the requirements file
# COPY requirements.txt .
#
# Run uv install within the Nix flake environment.
# This command enters the default dev shell defined in flake.nix and runs uv.
# RUN nix develop .#default --command bash -c "uv pip install -r requirements.txt"
# --- End Optional Section ---

# Set the default command to run the Python script using the flake's default shell.
# This ensures the script runs within the environment defined in flake.nix,
# where python3, chromedriver, and uv are available.
# CMD ["nix", "develop", ".#default", "--extra-experimental-features","flakes", "--extra-experimental-features","nix-command", "--command", "python", "main.py"]

# Alternatively, you could build a container layer with the environment:
RUN nix profile install .#default --extra-experimental-features nix-command --extra-experimental-features flakes
RUN uv sync

COPY . .
CMD ["uv","run", "main.py"]
# This second approach might be slightly faster at runtime but increases build time.
