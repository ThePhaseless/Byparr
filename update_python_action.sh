#!/bin/sh

action_path=.github/workflows/docker-publish.yml

# Example usage:
# ./update_python_action.sh python 3.12 3.13
dependency_name=$1
current_version=$2
new_version=$3

# If package is not python, skip
if [ "$dependency_name" != "python" ]; then
    exit 0
fi

# Find and replace python version
#         with:
#           python-version: "3.13"

sed -i "s/python-version: \"$current_version\"/python-version: \"$new_version\"/g" $action_path