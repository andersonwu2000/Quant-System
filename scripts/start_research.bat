@echo off
echo === Starting Alpha Research System ===
echo.

echo [Terminal 1] Starting research daemon...
start "Research Daemon" cmd /k "cd /d D:\Finance && python -m scripts.alpha_research_agent --daemon --interval 10"

echo [Terminal 2] Starting paper trading monitor...
start "Paper Monitor" cmd /k "cd /d D:\Finance && python -m scripts.paper_trading_monitor --daemon --interval 3600"

echo.
echo === Both processes started in separate windows ===
echo.
echo To start hypothesis generator (Terminal 3):
echo   cd D:\Finance ^&^& claude -p scripts/hypothesis_generator_prompt.txt
echo.
pause
