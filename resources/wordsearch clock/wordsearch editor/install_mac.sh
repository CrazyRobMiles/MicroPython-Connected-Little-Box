#!/usr/bin/env bash
# install_mac.sh
# Sets up a virtual environment and installs the Wordsearch Editor dependencies on macOS.
# Run from the project folder that contains WordsearchEditor.py and requirements.txt

set -euo pipefail

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 was not found."
  echo "Install Python first. Homebrew can install it with:"
  echo "  brew install python3"
  exit 1
fi

echo "Creating virtual environment..."
python3 -m venv .venv

echo "Activating virtual environment..."
source .venv/bin/activate

echo "Upgrading pip..."
python -m pip install --upgrade pip

echo "Installing project requirements..."
pip install -r requirements.txt

echo
echo "Install complete."
echo "Activate later with:"
echo "  source .venv/bin/activate"
echo "Run the editor with:"
echo "  python WordsearchEditor.py"
