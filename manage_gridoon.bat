@echo off

if not exist "venv\" (
    python -m venv venv
    call .\venv\Scripts\activate
    pip install -r requirements.txt
    echo Virtual environment created.
) else (
    call .\venv\Scripts\activate
    echo Virtual environment already exists.
)

python "src\manage_gridoon.py"
pause