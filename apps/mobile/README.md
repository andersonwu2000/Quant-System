# Quant Mobile

Mobile client for the [Quant Trading System](https://github.com/andersonwu2000/Finance) backend. Built with React Native + Expo + TypeScript.

## Features

- **Dashboard** — Real-time NAV, daily P&L, position overview
- **Positions** — Full position list with unrealized P&L
- **Strategies** — Start/stop strategies, monitor status
- **Alerts** — Risk alert feed with WebSocket real-time updates
- **Settings** — System status, risk rule toggle, kill switch

## Setup

```bash
# Install Node.js 20+ first, then:
npm install

# Start development server
npm start

# Run on specific platform
npm run ios
npm run android
```

## Configuration

On first launch, enter:
1. **Server URL** — Your backend API address (e.g., `http://192.168.1.100:8000`)
2. **API Key** — The `QUANT_API_KEY` value from your backend `.env`

## Backend Dependency

This app requires the Quant Trading System backend running at `D:\Finance`. Start it with:

```bash
cd D:\Finance
make api
```

## Tech Stack

- **Expo** ~52 + Expo Router (file-based routing)
- **React Native** 0.76
- **TypeScript** 5.3 (strict mode)
- **Expo Secure Store** for credential storage
- **WebSocket** for real-time portfolio/alert updates
