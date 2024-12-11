#!/bin/sh

# Source .venv
. .venv/bin/activate

# Fix for actions LD_LIBRARY_PATH env
touch ld_fix.sh
PYTHON_PATH=$(which python3)
PYTHON_DIR=$(dirname $PYTHON_PATH)
echo "export LD_LIBRARY_PATH=$PYTHON_DIR/../lib" >> ld_fix.sh
echo "export PATH=$PYTHON_DIR:\$PATH" >> ld_fix.sh
chmod +x ld_fix.sh