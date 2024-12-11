#!/bin/sh

if [ -f ld_fix.sh ]; then
    . ./ld_fix.sh
fi

uv run main.py