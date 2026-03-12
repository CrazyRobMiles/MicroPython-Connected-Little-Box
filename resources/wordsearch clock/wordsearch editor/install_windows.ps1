# install_windows.ps1
# Creates a local virtual environment and installs PyQt5 for the Wordsearch Editor.
# Run from the project folder that contains WordsearchEditor.py and requirements.txt

$ErrorActionPreference = "Stop"

Write-Host "Checking for Python launcher..."
try {
    py --version | Out-Null
} catch {
    Write-Error "Python launcher 'py' was not found. Install Python from python.org and enable 'Add Python to PATH'."
    exit 1
}

if (-not (Test-Path ".\requirements.txt")) {
    Write-Warning "requirements.txt was not found in the current folder."
}

Write-Host "Creating virtual environment..."
py -m venv .venv

Write-Host "Activating virtual environment..."
& ".\.venv\Scripts\Activate.ps1"

Write-Host "Upgrading pip..."
python -m pip install --upgrade pip

Write-Host "Installing project requirements..."
pip install -r requirements.txt

Write-Host ""
Write-Host "Install complete."
Write-Host "Activate later with:"
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host "Run the editor with:"
Write-Host "  python WordsearchEditor.py"
