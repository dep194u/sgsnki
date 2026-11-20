@echo off
cd /d "%~dp0"
if not exist venv (
  echo Creating Python environment...
  py -m venv venv
)
call venv\Scripts\activate
echo Installing or checking required packages...
python -m pip install -r requirements.txt
echo.
echo Starting ClipGenius AI...
echo Keep this window open while using the app.
start "" http://127.0.0.1:5000
python app.py
pause
