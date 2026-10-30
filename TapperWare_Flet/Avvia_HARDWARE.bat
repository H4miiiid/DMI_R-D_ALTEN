@echo off
cd /d "%~dp0"
python DmiGUI.pyw
if errorlevel 1 pause
