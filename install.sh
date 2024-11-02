#!/bin/bash
# Download the script
curl -O https://github.com/getinstachip/vpm-v2/raw/main/cli.py
# Make it executable
chmod +x cli.py
# Create an alias in .bashrc
echo "alias vpm='python $(pwd)/cli.py'" >> ~/.bashrc
source ~/.bashrc
