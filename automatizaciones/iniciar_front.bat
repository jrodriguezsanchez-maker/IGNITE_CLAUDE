@echo off
cd /d "%~dp0app"
start "" http://127.0.0.1:8765
python server.py
