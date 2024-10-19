#!/bin/sh

./run_vnc.sh

# Activate virtual environment
. .venv/bin/activate && python3 main.py