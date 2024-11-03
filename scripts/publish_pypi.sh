#!/bin/bash

# Remove existing dist files
rm -rf dist/*

# Build the package
python -m build

# Upload to PyPI using twine
python -m twine upload dist/*
