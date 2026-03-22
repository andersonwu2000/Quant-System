#!/usr/bin/env bash
# Quick start: backend + frontend
set -e

echo "========================================"
echo "  Quant Trading System - Quick Start"
echo "========================================"
echo ""

# Start backend in background
echo "[1/2] Starting backend API (port 8000)..."
(cd /d/Finance && python -m uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000) &
BACKEND_PID=$!

sleep 2

# Start frontend in background
echo "[2/2] Starting frontend dev server (port 3000)..."
(cd /d/Ursa-Major/projects/quant-web && npm run dev) &
FRONTEND_PID=$!

sleep 2

echo ""
echo "========================================"
echo "  Backend:  http://localhost:8000/docs"
echo "  Frontend: http://localhost:3000"
echo "========================================"
echo ""
echo "Press Ctrl+C to stop both servers"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
