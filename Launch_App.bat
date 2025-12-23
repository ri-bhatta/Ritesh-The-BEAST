@echo off
echo ===================================
echo   IBPS BEAST ULTIMATE SYSTEM
echo ===================================
echo 1. Launch Student App (Doctor Mode)
echo 2. Launch Admin Content Generator
set /p choice="Select: "
if "%choice%"=="1" streamlit run app_master.py
if "%choice%"=="2" streamlit run uploader.py
pause

