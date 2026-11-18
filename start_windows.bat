@echo off
cd /d "%~dp0"
py -3.11 -m pip install -r requirements.txt
if errorlevel 1 pause & exit /b 1
py -3.11 -m streamlit run app.py
pause
