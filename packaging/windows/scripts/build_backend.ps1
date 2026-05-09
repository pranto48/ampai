$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot/../../.."

python -m venv .venv-winbuild
. .\.venv-winbuild\Scripts\Activate.ps1
python -m pip install --upgrade pip wheel
pip install -r backend/requirements.txt
pip install pyinstaller

pyinstaller --noconfirm --clean --name ampai-backend --distpath dist/windows/stage/backend --workpath dist/windows/.pyi-work --specpath dist/windows/.pyi-spec backend/main.py
