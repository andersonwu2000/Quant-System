@echo off
chcp 65001 >nul
title Quant Trading - Full Stack + Tunnel

echo ========================================
echo   Quant Trading System - Quick Start
echo   (with ngrok Tunnel for Mobile)
echo ========================================
echo.

:: Start backend
echo [1/3] Starting backend API (port 8000)...
cd /d %~dp0..
start "Quant-API" cmd /k "chcp 65001 >nul & title Quant API & python -m uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000"

:: Wait for backend to be ready
echo       Waiting for API to start...
timeout /t 5 /nobreak >nul

:: Start frontend
echo [2/3] Starting frontend dev server (port 3000)...
cd /d %~dp0..\apps\web
start "Quant-Web" cmd /k "title Quant Web & bun run dev"

:: Start ngrok Tunnel (fixed domain)
echo [3/3] Starting ngrok Tunnel (fixed domain)...
cd /d %~dp0..
start "Quant-Tunnel" cmd /k "chcp 65001 >nul & title Quant Tunnel & npx ngrok http 8000 --url=lorie-zoomorphic-rogelio.ngrok-free.dev"

timeout /t 5 /nobreak >nul

echo.
echo ============================================
echo   Backend:  http://localhost:8000/docs
echo   Frontend: http://localhost:3000
echo   Tunnel:   https://lorie-zoomorphic-rogelio.ngrok-free.dev
echo ============================================
echo.
echo   Mobile App:
echo     Server URL : https://lorie-zoomorphic-rogelio.ngrok-free.dev
echo     Username   : admin
echo     Password   : Admin1234
echo ============================================
echo.
pause
