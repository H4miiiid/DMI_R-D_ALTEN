@echo off
cd /d "%~dp0"
python DmiGUI.pyw --demo
if errorlevel 1 pause
