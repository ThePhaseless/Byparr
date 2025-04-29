# Dockerfile
# Use an official Nix image as the base
FROM nixos/nix:latest

# Set the working directory inside the container
WORKDIR /app

# Copy the shell.nix file first to define the environment.
# Copying this separately leverages Docker layer caching if shell.nix doesn't change.
COPY shell.nix pyproject.toml uv.lock ./

# --- Optional: Install Python dependencies using uv ---
# If you have a requirements.txt (or pyproject.toml), uncomment and adapt the following lines.
# Copy the requirements file
# COPY requirements.txt .
#
# Run uv install within the Nix environment defined by shell.nix
# This ensures dependencies are installed using the Python from the Nix environment.
RUN nix-shell --run "uv sync"
# --- End Optional Section ---

# Set the default command to run the Python script using nix-shell.
# This ensures the script runs within the environment where python3, chromedriver,
# and uv (and potentially installed Python packages) are available.
CMD ["nix-shell", "--run", "uv run main.py"]
