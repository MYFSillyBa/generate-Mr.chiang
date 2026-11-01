@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist "讲解石生成器.exe" (
    start "" "%~dp0讲解石生成器.exe"
    exit /b
)
python app.py
if errorlevel 1 pause
