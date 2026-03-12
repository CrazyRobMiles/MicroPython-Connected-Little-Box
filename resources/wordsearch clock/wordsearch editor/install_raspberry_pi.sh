#!/usr/bin/env bash
# install_raspberry_pi.sh
# Sets up a virtual environment and installs the Wordsearch Editor dependencies on Raspberry Pi OS.
# Run from the project folder that contains WordsearchEditor.py and requirements.txt

set -euo pipefail

echo "Updating package lists..."
sudo apt update

echo "Installing Python and venv support..."
sudo apt install -y python3 python3-venv python3-pip python3-full

echo "Creating virtual environment..."
python3 -m venv .venv

echo "Activating virtual environment..."
source .venv/bin/activate

echo "Upgrading pip..."
python -m pip install --upgrade pip

echo "Installing project requirements from PyPI..."
pip install -r requirements.txt

echo
echo "Install complete."
echo "Activate later with:"
echo "  source .venv/bin/activate"
echo "Run the editor with:"
echo "  python WordsearchEditor.py"
