@echo off
chcp 65001 >nul
title Cloudflare Named Tunnel Setup

echo =====================================================
echo   Cloudflare Named Tunnel Setup (one-time)
echo   This gives you a FIXED URL for your Mobile App
echo =====================================================
echo.
echo   Prerequisites:
echo     1. Free Cloudflare account (https://dash.cloudflare.com/sign-up)
echo     2. A domain added to Cloudflare (even a free one works)
echo.
echo   Steps:
echo.
echo   [Step 1] Login to Cloudflare (opens browser):
echo     cloudflared tunnel login
echo.
echo   [Step 2] Create a named tunnel:
echo     cloudflared tunnel create quant-api
echo.
echo   [Step 3] Route DNS (replace YOUR_DOMAIN):
echo     cloudflared tunnel route dns quant-api api.YOUR_DOMAIN.com
echo.
echo   [Step 4] Run tunnel (use this every time):
echo     cloudflared tunnel run --url http://localhost:8000 quant-api
echo.
echo   After setup, your FIXED URL will be:
echo     https://api.YOUR_DOMAIN.com
echo.
echo   Then update .env:
echo     QUANT_ALLOWED_ORIGINS=["http://localhost:3000","https://api.YOUR_DOMAIN.com"]
echo.
echo =====================================================
echo.
echo Starting interactive setup...
echo.

:: Step 1
echo [Step 1/3] Opening Cloudflare login in browser...
cloudflared tunnel login
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Login failed. Please try again.
    pause
    exit /b 1
)
echo Login successful!
echo.

:: Step 2
echo [Step 2/3] Creating named tunnel "quant-api"...
cloudflared tunnel create quant-api
if %ERRORLEVEL% NEQ 0 (
    echo NOTE: Tunnel may already exist. Continuing...
)
echo.

echo [Step 3/3] Setup complete!
echo.
echo   Next: Run the following to link a DNS record:
echo     cloudflared tunnel route dns quant-api api.YOUR_DOMAIN.com
echo.
echo   Then start with:
echo     cloudflared tunnel run --url http://localhost:8000 quant-api
echo.
pause
