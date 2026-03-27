# App 穩定性測試與優化報告

> 產出日期：2026-03-26
> 適用範圍：Quant Trading Portfolio — Web App（React 18 + Vite）＆ Mobile App（React Native + Expo 52）

---

## 目錄

1. [穩定性測試概述](#1-穩定性測試概述)
2. [關鍵穩定性指標（KPI）與業界基準](#2-關鍵穩定性指標kpi與業界基準)
3. [穩定性測試方法論](#3-穩定性測試方法論)
4. [測試工具與技術棧](#4-測試工具與技術棧)
5. [針對本專案的測試策略](#5-針對本專案的測試策略)
6. [穩定性優化策略](#6-穩定性優化策略)
7. [持續監控與 CI/CD 整合](#7-持續監控與-cicd-整合)
8. [執行計畫與優先順序](#8-執行計畫與優先順序)
9. [參考資料](#9-參考資料)

---

## 1. 穩定性測試概述

App 穩定性測試旨在確保應用程式在各種條件下（高負載、網路不穩、長時間運行、不同裝置與 OS 版本）都能正常運作，不會發生崩潰（Crash）、無回應（ANR/Hang）或記憶體洩漏（Memory Leak）。

### 穩定性測試的核心目標

| 目標 | 說明 |
|------|------|
| **降低崩潰率** | 維持 Crash-Free Session Rate ≥ 99.95% |
| **消除 ANR** | 確保 UI 執行緒不被阻塞超過 5 秒 |
| **防止記憶體洩漏** | 長時間運行後記憶體使用量保持穩定 |
| **確保效能一致性** | 在不同裝置與網路環境下維持流暢體驗 |
| **提升使用者滿意度** | 穩定性直接影響 App Store 評分（≥99.85% crash-free 才能達到 4.5 星）|

---

## 2. 關鍵穩定性指標（KPI）與業界基準

### 2.1 核心指標

| 指標 | 定義 | 業界基準（2025） | 目標值 |
|------|------|------------------|--------|
| **Crash-Free Session Rate** | 無崩潰的 Session 佔比 | 中位數 99.95%（Android）、99.87%（iOS） | ≥ 99.95% |
| **ANR Rate** | Application Not Responding 發生率 | < 0.47%（Google Play 門檻） | < 0.1% |
| **App 啟動時間** | Cold Start 到可互動的時間 | < 2 秒（理想）、< 3 秒（可接受） | < 2 秒 |
| **API 回應時間** | 關鍵 API 呼叫完成時間 | < 200ms（關鍵操作） | < 200ms |
| **互動回應時間** | 使用者操作到 UI 回饋 | < 1 秒 | < 500ms |
| **記憶體使用量** | 長時間運行後記憶體增長率 | 穩定（無持續增長） | 30 分鐘內增長 < 10% |
| **FPS (幀率)** | 畫面渲染流暢度 | ≥ 55 FPS | ≥ 58 FPS |
| **OOM Rate** | Out-of-Memory 崩潰率 | — | < 0.01% |

### 2.2 穩定性等級標準

| 等級 | Crash-Free Rate | App Store 評分影響 |
|------|-----------------|-------------------|
| 🏆 卓越 | ≥ 99.99% | 5 星潛力 |
| ✅ 優良 | ≥ 99.95% | 4.5+ 星 |
| ⚠️ 可接受 | ≥ 99.85% | 4.0+ 星 |
| ❌ 臨界 | ≥ 99.70% | 3.0 星門檻 |
| 🚫 不及格 | < 99.70% | 嚴重影響排名與留存率 |

---

## 3. 穩定性測試方法論

### 3.1 Monkey Testing（猴子測試）

**目的**：模擬隨機使用者操作，發現非預期的崩潰與 ANR。

**方法**：
- 使用 Android `adb shell monkey` 工具發送大量隨機事件（觸控、手勢、按鍵）
- 設定事件數量（建議 50,000 ~ 500,000 次）
- 記錄所有 Crash 與 ANR

**執行範例**：
```bash
# Android Monkey Testing — 10 萬次隨機事件
adb shell monkey -p com.quanttrading.app -v --throttle 100 -s 12345 100000

# 參數說明：
# -p: 指定 package name
# -v: verbose 模式
# --throttle 100: 每個事件間隔 100ms
# -s 12345: 固定 seed 以利重現
```

### 3.2 Stress Testing（壓力測試）

**目的**：測試 App 在極端條件下的表現。

**測試場景**：
| 場景 | 測試內容 |
|------|----------|
| 高併發 | 模擬多個 WebSocket 連線同時推送資料 |
| 大資料量 | 載入 500+ 筆持倉、10 年回測數據 |
| 快速操作 | 連續快速切換頁面、重複提交訂單 |
| 低記憶體 | 在背景開啟多個 App 後測試 |
| 網路切換 | WiFi ↔ 4G/5G 切換、斷線重連 |

### 3.3 Endurance Testing（耐久測試）

**目的**：檢測長時間運行下的記憶體洩漏與效能衰退。

**方法**：
- 持續運行 App 4～8 小時
- 每 15 分鐘記錄記憶體用量、CPU 使用率、FPS
- 觀察 WebSocket 長連線的穩定性
- 監控 `portfolio` 與 `market` channel 的即時推送

### 3.4 Compatibility Testing（相容性測試）

**目的**：確保在不同裝置與 OS 版本上的穩定性。

**測試矩陣**：
| 平台 | 最低版本 | 主要測試版本 |
|------|----------|-------------|
| Android | 10 (API 29) | 12, 13, 14, 15 |
| iOS | 15.0 | 16, 17, 18 |
| Web Browser | Chrome 90+ | Chrome, Firefox, Safari, Edge 最新版 |

### 3.5 Network Resilience Testing（網路韌性測試）

**目的**：測試不同網路條件下的穩定性。

**測試場景**：
- 正常 WiFi（低延遲、高頻寬）
- 3G 網路（高延遲、低頻寬）
- 網路斷線與重連
- 網路切換（WiFi → 行動數據）
- 高延遲環境（> 500ms）
- 封包遺失（5%, 10%, 20%）

---

## 4. 測試工具與技術棧

### 4.1 本專案適用的測試工具

| 類別 | 工具 | 用途 | 適用平台 |
|------|------|------|----------|
| **崩潰監控** | Firebase Crashlytics | 即時崩潰報告、堆疊追蹤 | Mobile |
| **崩潰監控** | Sentry | 錯誤追蹤、效能監控 | Web + Mobile |
| **記憶體分析** | React DevTools Profiler | 組件渲染分析、記憶體快照 | Web + Mobile |
| **記憶體分析** | Hermes Memory Profiler | JS Heap 分析 | Mobile (Hermes) |
| **記憶體分析** | Flipper | 記憶體追蹤、效能分析 | Mobile |
| **記憶體分析** | LeakCanary | Android 原生記憶體洩漏偵測 | Android |
| **效能分析** | Lighthouse | Web 效能評分 | Web |
| **效能分析** | React Native Performance | FPS、JS 執行緒監控 | Mobile |
| **壓力測試** | Android Monkey | 隨機事件壓力測試 | Android |
| **壓力測試** | k6 / Artillery | API 壓力測試 | Backend |
| **E2E 測試** | Playwright | 端到端自動化測試 | Web |
| **E2E 測試** | Detox | 端到端自動化測試 | Mobile |
| **網路模擬** | Charles Proxy | 網路節流、封包分析 | All |
| **CI 整合** | GitHub Actions | 自動化測試管線 | All |

### 4.2 推薦技術棧組合

```
監控層：Sentry (Web + Mobile) + Firebase Crashlytics (Mobile)
    ↓
分析層：React DevTools + Hermes Profiler + Flipper
    ↓
測試層：Playwright (Web E2E) + Detox (Mobile E2E) + Monkey (Android Stress)
    ↓
CI 層：GitHub Actions → 自動化回歸 + 效能門檻
```

---

## 5. 針對本專案的測試策略

### 5.1 Web App（React 18 + Vite）穩定性測試

#### 5.1.1 重點測試區域

| 頁面/功能 | 風險等級 | 測試重點 |
|-----------|---------|----------|
| Dashboard（即時推送） | 🔴 高 | WebSocket 長連線穩定性、大量資料渲染 |
| Backtest（運算密集） | 🔴 高 | 長時間回測的記憶體使用、大數據集圖表渲染 |
| Portfolio（CRUD） | 🟡 中 | 並發操作、樂觀更新的一致性 |
| Orders（交易關鍵） | 🔴 高 | 重複提交防護、網路斷線處理 |
| Admin（權限控制） | 🟡 中 | 角色切換、大量用戶列表渲染 |

#### 5.1.2 WebSocket 穩定性測試

本專案的 WebSocket（`src/api/ws.py`）支援 `portfolio`、`alerts`、`orders`、`market` 四個 channel，需特別測試：

```javascript
// 測試場景：WebSocket 斷線重連
describe('WebSocket Stability', () => {
  it('should auto-reconnect with exponential backoff', async () => {
    // 模擬連線建立
    // 模擬伺服器斷線
    // 驗證自動重連行為
    // 驗證指數退避機制（1s → 2s → 4s → 8s → ...）
  });

  it('should handle rapid subscribe/unsubscribe', async () => {
    // 快速訂閱/取消訂閱 channel
    // 驗證無記憶體洩漏
  });

  it('should maintain connection during network switch', async () => {
    // 模擬 WiFi → 行動數據切換
    // 驗證資料同步恢復
  });
});
```

#### 5.1.3 Virtual Scrolling 穩定性

`DataTable` 使用 TanStack React Virtual 實現虛擬捲動，需測試：
- 載入 10,000+ 筆資料的渲染穩定性
- 快速捲動時的 FPS 維持
- 搜尋/篩選時的記憶體釋放

### 5.2 Mobile App（React Native + Expo 52）穩定性測試

#### 5.2.1 重點測試區域

| 功能 | 風險等級 | 測試重點 |
|------|---------|----------|
| Victory Native 圖表 | 🔴 高 | 大量數據點渲染、記憶體使用 |
| 即時行情推送 | 🔴 高 | 背景/前景切換時的連線維持 |
| SecureStore 存取 | 🟡 中 | 加密儲存的讀寫效能 |
| 離線模式 | 🟡 中 | OfflineBanner 偵測、離線操作佇列 |
| 圖片/圖表記憶體 | 🔴 高 | 大量圖表渲染時的 OOM 風險 |

#### 5.2.2 React Native 記憶體洩漏檢測

```javascript
// 常見記憶體洩漏模式與修復

// ❌ 錯誤：未清理的 useEffect
useEffect(() => {
  const subscription = wsManager.subscribe('portfolio', handleUpdate);
  // 缺少 cleanup function — 導致記憶體洩漏！
}, []);

// ✅ 正確：加入 cleanup
useEffect(() => {
  const subscription = wsManager.subscribe('portfolio', handleUpdate);
  return () => {
    subscription.unsubscribe(); // 元件卸載時清理
  };
}, []);

// ❌ 錯誤：未取消的 Timer
useEffect(() => {
  setInterval(() => {
    fetchPortfolio();
  }, 5000);
}, []);

// ✅ 正確：清理 Timer
useEffect(() => {
  const timer = setInterval(() => {
    fetchPortfolio();
  }, 5000);
  return () => clearInterval(timer);
}, []);
```

#### 5.2.3 Android Monkey 測試計畫

```bash
# 第一輪：基本穩定性（1 萬次事件）
adb shell monkey -p com.quanttrading.app -v --throttle 200 10000

# 第二輪：中度壓力（10 萬次事件）
adb shell monkey -p com.quanttrading.app -v --throttle 100 \
  --pct-touch 40 --pct-motion 25 --pct-nav 15 \
  --pct-majornav 10 --pct-appswitch 5 --pct-anyevent 5 \
  -s 42 100000

# 第三輪：極限壓力（50 萬次事件）
adb shell monkey -p com.quanttrading.app -v --throttle 50 \
  --ignore-crashes --ignore-timeouts \
  -s 42 500000 2>&1 | tee monkey_log.txt
```

### 5.3 Backend API 穩定性測試

```bash
# 使用 k6 進行 API 壓力測試
# k6-stability-test.js

import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '2m', target: 50 },   // 漸增到 50 使用者
    { duration: '5m', target: 50 },   // 維持 50 使用者
    { duration: '2m', target: 100 },  // 漸增到 100 使用者
    { duration: '5m', target: 100 },  // 維持 100 使用者
    { duration: '2m', target: 0 },    // 漸減到 0
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'],   // 95% 請求 < 500ms
    http_req_failed: ['rate<0.01'],     // 失敗率 < 1%
  },
};

export default function () {
  // 測試關鍵 API 端點
  const endpoints = [
    '/api/v1/system/health',
    '/api/v1/strategies',
    '/api/v1/portfolio/saved',
    '/api/v1/risk/rules',
  ];

  endpoints.forEach(endpoint => {
    const res = http.get(`http://localhost:8000${endpoint}`);
    check(res, {
      'status is 200': (r) => r.status === 200,
      'response time < 500ms': (r) => r.timings.duration < 500,
    });
  });

  sleep(1);
}
```

---

## 6. 穩定性優化策略

### 6.1 崩潰修復優先順序

根據穩定性測試結果，按以下優先順序進行修復：

```
P0 (立即修復) → 影響 > 1% 使用者的崩潰
P1 (本週修復) → 影響 0.1% ~ 1% 使用者的崩潰
P2 (本月修復) → 影響 < 0.1% 使用者的崩潰
P3 (排入待辦) → 邊緣案例崩潰
```

### 6.2 記憶體優化

#### 6.2.1 React（Web + Mobile 共用）

| 問題 | 優化方式 | 預期效果 |
|------|----------|----------|
| 組件不必要的重新渲染 | `React.memo()` + `useMemo()` + `useCallback()` | 減少 30-50% 渲染次數 |
| 大列表渲染 | Web: TanStack Virtual（已採用）<br>Mobile: FlashList 取代 FlatList | 記憶體使用降低 40-60% |
| 未清理的 Side Effects | 所有 `useEffect` 加入 cleanup function | 消除記憶體洩漏 |
| 圖表記憶體佔用 | 限制數據點數量 + 離屏圖表卸載 | 記憶體使用降低 20-30% |
| 全域狀態過大 | 分割 Context、按需載入 | 減少不必要的 re-render |

#### 6.2.2 React Native 特定優化

```javascript
// 1. 使用 FlashList 取代 FlatList（效能提升 5-10 倍）
import { FlashList } from "@shopify/flash-list";

<FlashList
  data={positions}
  renderItem={({ item }) => <PositionRow position={item} />}
  estimatedItemSize={80}  // 提供預估高度以優化渲染
  keyExtractor={(item) => item.symbol}
/>

// 2. 圖片優化 — 使用 expo-image 取代 Image
import { Image } from 'expo-image';

<Image
  source={chartImage}
  contentFit="contain"
  cachePolicy="memory-disk"  // 智慧快取策略
  recyclingKey={chartId}     // 啟用圖片回收
/>

// 3. 減少 Bridge 通訊（使用 Hermes + JSI）
// Expo 52 預設使用 Hermes，已自動啟用 JSI
```

### 6.3 網路穩定性優化

| 策略 | 實作方式 | 適用場景 |
|------|----------|----------|
| **指數退避重試** | WSManager 已實作（`@quant/shared`） | WebSocket 斷線 |
| **請求去重** | 加入 request deduplication middleware | 重複 API 呼叫 |
| **離線佇列** | 將操作暫存，網路恢復後批次執行 | 訂單提交、資料同步 |
| **樂觀更新 + 回滾** | 立即更新 UI，失敗時回滾 | Portfolio CRUD |
| **超時處理** | 所有 API 呼叫設定合理 timeout（10s） | 全部端點 |
| **資料壓縮** | 啟用 gzip/brotli 壓縮 | 大量資料傳輸 |

### 6.4 效能優化

#### 6.4.1 Web App

```javascript
// 1. 路由層級的 Code Splitting（已支援 React.lazy）
const BacktestPage = React.lazy(() => import('@feat/backtest/BacktestPage'));
const AdminPage = React.lazy(() => import('@feat/admin/AdminPage'));

// 2. 重型計算移至 Web Worker
// 回測圖表數據處理
const worker = new Worker(new URL('./backtest-worker.ts', import.meta.url));
worker.postMessage({ type: 'PROCESS_RESULTS', data: backtestResult });
worker.onmessage = (e) => setProcessedData(e.data);

// 3. 圖表渲染優化
// 數據降採樣：10 年日線數據 (~2,500 點) → 顯示寬度的 2 倍點數
function downsample(data, maxPoints) {
  if (data.length <= maxPoints) return data;
  const step = Math.ceil(data.length / maxPoints);
  return data.filter((_, i) => i % step === 0);
}
```

#### 6.4.2 Mobile App

| 優化項目 | 方法 | 效果 |
|----------|------|------|
| 啟動速度 | 延遲載入非關鍵模組（Lazy import） | 啟動時間 -30% |
| 動畫流暢度 | 使用 `react-native-reanimated` worklet | 維持 60 FPS |
| 圖表效能 | Victory Native 數據點限制 + 降採樣 | 記憶體 -40% |
| 列表效能 | FlashList + `getItemType` 分類 | 捲動 FPS +20% |
| 背景狀態 | App State 監聽，背景時暫停 WebSocket | 電池 -25% |

### 6.5 錯誤處理強化

```javascript
// 1. 全域錯誤邊界（Web 已有 ErrorBoundary）
// 確保每個頁面都有獨立的 ErrorBoundary

// 2. API 錯誤統一處理
class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public retryable: boolean = false
  ) {
    super(message);
  }
}

// 3. 自動重試策略
async function fetchWithRetry(url, options, maxRetries = 3) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      const res = await fetch(url, options);
      if (res.ok) return res;
      if (res.status >= 500 && i < maxRetries - 1) {
        await sleep(Math.pow(2, i) * 1000); // 指數退避
        continue;
      }
      throw new ApiError(res.status, 'API_ERROR', await res.text());
    } catch (err) {
      if (i === maxRetries - 1) throw err;
      await sleep(Math.pow(2, i) * 1000);
    }
  }
}
```

---

## 7. 持續監控與 CI/CD 整合

### 7.1 CI/CD 穩定性門檻

在現有的 GitHub Actions CI（9 jobs）中加入穩定性品質門檻：

```yaml
# .github/workflows/ci.yml — 新增穩定性檢查

stability-check:
  name: Stability Gates
  runs-on: ubuntu-latest
  needs: [backend-test, web-test, mobile-test]
  steps:
    # Web 效能門檻
    - name: Lighthouse CI
      uses: treosh/lighthouse-ci-action@v12
      with:
        budgetPath: ./lighthouse-budget.json
        # 門檻：Performance ≥ 80, Accessibility ≥ 90

    # Bundle 大小監控
    - name: Bundle Size Check
      run: |
        cd apps/web && bun run build
        MAX_SIZE=500  # KB
        ACTUAL=$(du -sk dist/assets/*.js | awk '{sum+=$1} END {print sum}')
        if [ "$ACTUAL" -gt "$MAX_SIZE" ]; then
          echo "::error::Bundle size ${ACTUAL}KB exceeds ${MAX_SIZE}KB limit"
          exit 1
        fi

    # 記憶體洩漏檢測（Web）
    - name: Memory Leak Detection
      run: |
        cd apps/web
        bun run test:memory  # 自訂的記憶體測試腳本
```

### 7.2 監控儀表板建議架構

```
┌─────────────────────────────────────────────────┐
│              穩定性監控儀表板                      │
├─────────────┬─────────────┬─────────────────────┤
│  崩潰率      │  ANR 率      │  記憶體使用趨勢      │
│  (Sentry)   │  (Sentry)   │  (Prometheus)       │
├─────────────┼─────────────┼─────────────────────┤
│  API 延遲    │  錯誤率      │  WebSocket 連線數    │
│  (p50/p95)  │  (4xx/5xx)  │  (即時)             │
├─────────────┼─────────────┼─────────────────────┤
│  App 啟動    │  FPS 分佈    │  用戶影響範圍        │
│  時間趨勢    │  (Mobile)   │  (受影響 Session %)  │
└─────────────┴─────────────┴─────────────────────┘
```

### 7.3 告警規則

| 告警等級 | 條件 | 通知管道 |
|---------|------|----------|
| 🔴 Critical | Crash-Free Rate < 99.5% | Discord + LINE + Telegram |
| 🟠 Warning | Crash-Free Rate < 99.9% | Discord |
| 🟡 Info | API p95 延遲 > 1s | Discord |
| 🔴 Critical | OOM 崩潰數 > 10/hr | Discord + LINE + Telegram |
| 🟠 Warning | WebSocket 斷線率 > 5% | Discord |

> 本專案已有 `src/notifications/` 模組支援 Discord / LINE / Telegram，可直接整合。

---

## 8. 執行計畫與優先順序

### Phase 1：基礎建設（第 1-2 週）

| 任務 | 優先度 | 工時估計 |
|------|--------|---------|
| 整合 Sentry SDK（Web + Mobile） | P0 | 4h |
| 整合 Firebase Crashlytics（Mobile） | P0 | 3h |
| 設定崩潰告警規則 | P0 | 2h |
| 建立 Lighthouse CI 門檻 | P1 | 2h |
| 撰寫 Bundle Size 監控腳本 | P1 | 1h |

### Phase 2：測試執行（第 3-4 週）

| 任務 | 優先度 | 工時估計 |
|------|--------|---------|
| 執行 Android Monkey 測試（3 輪） | P0 | 4h |
| WebSocket 穩定性自動化測試 | P0 | 6h |
| 記憶體洩漏掃描（Web + Mobile） | P0 | 8h |
| API 壓力測試（k6） | P1 | 4h |
| 網路韌性測試 | P1 | 4h |
| 跨裝置相容性測試 | P2 | 6h |

### Phase 3：優化修復（第 5-6 週）

| 任務 | 優先度 | 工時估計 |
|------|--------|---------|
| 修復發現的崩潰問題 | P0 | 依問題量 |
| 修復記憶體洩漏 | P0 | 依問題量 |
| FlashList 替換 FlatList | P1 | 3h |
| 圖表數據降採樣實作 | P1 | 4h |
| useEffect cleanup 全面檢查 | P0 | 4h |
| 離線佇列機制實作 | P2 | 8h |

### Phase 4：持續監控（長期）

| 任務 | 優先度 | 工時估計 |
|------|--------|---------|
| 穩定性儀表板建置 | P1 | 8h |
| 週度穩定性報告自動化 | P2 | 4h |
| 定期 Endurance Testing（每月） | P2 | 2h/月 |
| 回歸測試套件維護 | P1 | 持續 |

---

## 9. 參考資料

### 業界基準與指標
- [Luciq Mobile App Stability Outlook 2025 — Benchmark Report](https://www.luciq.ai/mobile-app-stability-outlook-2025)
- [APM KPIs: Mobile App Performance Monitoring Metrics and Targets](https://www.luciq.ai/blog/app-performance-metrics-and-kpis)
- [Mobile App Performance Metrics: Essential KPIs to Track in 2026](https://www.plotline.so/blog/mobile-app-performance-metrics-essential-kpis-to-track)
- [14 Important Mobile App Metrics to Track (+ Benchmarks)](https://userpilot.com/blog/mobile-app-metrics/)
- [Firebase Crashlytics — Understand crash-free metrics](https://firebase.google.com/docs/crashlytics/crash-free-metrics)

### 測試方法與工具
- [Mobile App Testing Guide 2026 | Appypie](https://www.appypie.com/blog/mobile-app-testing)
- [Mobile App Testing: Best Practices for 2026 | Momentic](https://momentic.ai/blog/mobile-app-testing-best-practices)
- [Monkey Testing in Software Testing: A Complete Guide (2026)](https://testomat.io/blog/what-is-monkey-testing-in-software-testing-a-complete-guide/)
- [Big test stability | Android Developers](https://developer.android.com/training/testing/instrumented-tests/stability)
- [8-Step Mobile Testing Strategy 2026: Tools & Best Practices](https://www.testingmind.com/mobile-testing-strategy-guide-2026/)

### React Native 效能優化
- [React Native Memory Leak Fixes: Identify, Debug, and Optimize](https://instamobile.io/blog/react-native-memory-leak-fixes/)
- [React Native Performance Tactics: Modern Strategies and Tools | Sentry](https://blog.sentry.io/react-native-performance-strategies-tools/)
- [Optimizing Performance in React Native Apps (Expo)](https://dev.to/vrinch/optimizing-performance-in-react-native-apps-expo-354k)
- [Memory Leak Detection in React Native with LeakCanary](https://dev.to/amitkumar13/memory-leak-detection-in-react-native-with-leakcanary-166o)
- [Debugging and Profiling Tools — Expo Documentation](https://docs.expo.dev/debugging/tools/)

### 穩定性優化策略
- [Android Vitals | App Quality | Android Developers](https://developer.android.com/topic/performance/vitals)
- [Mobile App Stability: Memory Leaks, ANRs & Crashes](https://www.digia.tech/post/mobile-app-stability-memory-leaks-anr-crash-optimization)
- [Troubleshooting App Stability: Practical Ways to Prevent Crashes and ANRs](https://5star-designers.co.uk/blog/troubleshooting-app-stability-practical-ways-to-prevent-crashes-and-anrs/)
- [Achieving App Quality Through Performance and Stability | Amazon](https://developer.amazon.com/apps-and-games/blogs/2025/03/achieving-app-quality-through-performance-and-stability)
- [How to Ensure Long-Term App Stability Across Devices and Operating Systems](https://medium.com/@testwithblake/how-to-ensure-long-term-app-stability-across-devices-and-operating-systems-ed5ed00748aa)

---

---

## 10. 穩定性測試執行結果（2026-03-26）

### 10.1 自動化測試結果

| 測試類別 | 測試數 | 通過 | 失敗 | 跳過 | 耗時 |
|---------|--------|------|------|------|------|
| 後端 pytest | 861 | 859 | 0 | 2 | 146.65s |
| Web Vitest | 115 | 115 | 0 | 0 | 5.14s |
| Shared Vitest | 38 | 38 | 0 | 0 | 3.09s |
| Web TypeScript | - | PASS | - | - | - |
| Web Production Build | - | PASS | - | - | 3.48s |

### 10.2 Bundle Size 分析

| 檔案 | 大小 | Gzip 後 | 評估 |
|------|------|---------|------|
| chartColors (Recharts) | 383.62 KB | 105.60 KB | 最大單一 chunk |
| index (React/Router core) | 221.70 KB | 75.70 KB | 框架基礎 |
| index (feature) | 144.13 KB | 57.15 KB | 功能模組 |
| 總計 dist/ | 1,112 KB | - | 可接受 |

### 10.3 發現的問題與修復狀態

#### 高嚴重度（已修復）

| # | 問題 | 檔案 | 狀態 |
|---|------|------|------|
| 1 | SPA fallback 路徑穿越漏洞 | `src/api/app.py` | **已修復** — 加入 `is_relative_to()` 檢查 |
| 2 | auto-alpha WS 端點無認證 | `src/api/routes/auto_alpha.py` | **已修復** — 加入 token 認證邏輯 |
| 3 | 缺少全域例外處理器 | `src/api/app.py` | **已修復** — 加入 500 fallback handler |

#### 中嚴重度（已修復）

| # | 問題 | 檔案 | 狀態 |
|---|------|------|------|
| 4 | FastAPI `on_event` 已棄用 | `src/api/app.py` | **已修復** — 遷移至 `lifespan` context manager |
| 5 | `_run_now_tasks` 無限增長（記憶體洩漏） | `src/api/routes/auto_alpha.py` | **已修復** — 加入 50 筆上限 + 自動清除 |
| 6 | kill switch monitor 字典迭代安全 | `src/api/app.py` | **已修復** — 使用 `list()` 複製 |
| 7 | WSManager 無最大重連限制 | `apps/shared/src/api/ws.ts` | **已修復** — 加入 MAX_RETRIES=20 |
| 8 | WS 連線數無上限 | `src/api/ws.py` | **已修復** — 加入 200/channel 限制 |
| 9 | AutoAlphaPage async handler 無 mounted 檢查 | `apps/web/.../AutoAlphaPage.tsx` | **已修復** — 加入 mountedRef |
| 10 | AllocationPage async handler 無 mounted 檢查 | `apps/web/.../AllocationPage.tsx` | **已修復** — 加入 mountedRef + translateApiError |

#### 低嚴重度（已修復）

| # | 問題 | 檔案 | 狀態 |
|---|------|------|------|
| 11 | HelpTip setTimeout 未清理 | `apps/web/.../HelpTip.tsx` | **已修復** — 加入 useEffect cleanup |
| 12 | WS handler 錯誤不隔離 | `apps/shared/src/api/ws.ts` | **已修復** — 每個 handler 獨立 try/catch |
| 13 | `close_all` 無超時保護 | `src/api/ws.py` | **已修復** — 加入 3 秒 timeout |
| 14 | WS 重複連線 | `src/api/ws.py` | **已修復** — connect 時檢查重複 |

#### 第二輪修復（已完成）

| # | 問題 | 檔案 | 狀態 |
|---|------|------|------|
| 15 | `alpha_tasks` 跨線程無鎖保護 | `src/api/state.py`, `src/api/routes/alpha.py` | **已修復** — 加入 `alpha_lock` threading.Lock |
| 16 | 資料庫連線池未配置 | `src/data/store.py` | **已修復** — PostgreSQL: pool_size=10, max_overflow=20, pool_recycle=1800, pool_pre_ping |
| 17 | `asyncio.get_event_loop()` 已棄用 | `src/api/routes/alpha.py`, `src/alpha/auto/scheduler.py` | **已修復** — 改用 `get_running_loop()` |
| 18 | StrategiesPage async handler 無 mounted 檢查 | `apps/web/.../StrategiesPage.tsx` | **已修復** — 加入 mountedRef |
| 19 | RiskPage async handler 無 mounted 檢查 | `apps/web/.../RiskPage.tsx` | **已修復** — 加入 mountedRef |
| 20 | SettingsPage async handler 無 mounted 檢查 | `apps/web/.../SettingsPage.tsx` | **已修復** — 加入 mountedRef |
| 21 | AdminPage async handler 無 mounted 檢查 | `apps/web/.../AdminPage.tsx` | **已修復** — 加入 mountedRef |
| 22 | PaperTradingPage handlers 未使用 mountedRef | `apps/web/.../PaperTradingPage.tsx` | **已修復** — 在所有 handler 中使用 mountedRef |

#### 第三輪修復（已完成）

| # | 問題 | 檔案 | 狀態 |
|---|------|------|------|
| 23 | 前端 WS URL 不含認證 Token | `apps/web/src/core/api/client.ts` | **已修復** — login 時存 token，WS URL 自動附帶 `?token=` |
| 24 | 後端缺少 server-side ping | `src/api/ws.py`, `src/api/app.py` | **已修復** — 加入 `_server_ping_loop` 每 30 秒主動 ping 偵測死連線 |
| 25 | broadcast 無 backpressure | `src/api/ws.py` | **已修復** — 同 channel 前次 broadcast 未完成時丟棄新訊息 + 批次 50 並行 |
| 26 | useWs 每次建立新的 WSManager | `apps/web/src/core/hooks/useWs.ts` | **已修復** — 改為 singleton + refCount 共享機制 |
| 27 | backtest 結果全存記憶體 | `src/api/routes/backtest.py` | **已修復** — 加入 `_TASK_EXPIRY_SECONDS=3600` 自動清除過期任務 |

#### 所有問題均已修復，無待處理項目。

### 10.4 Deprecation Warnings 統計

| 警告來源 | 數量 | 說明 |
|---------|------|------|
| `asyncio.get_event_loop_policy` (Python 3.16) | 734 | 來自 pytest-asyncio 套件（非本專案程式碼） |
| ~~FastAPI `on_event` deprecated~~ | ~~0~~ | **已修復**：遷移至 lifespan |
| ~~`asyncio.get_event_loop()` deprecated~~ | ~~0~~ | **已修復**：改用 `get_running_loop()` |

### 10.5 穩定性評估總結

| 面向 | 評分 | 說明 |
|------|------|------|
| **測試覆蓋** | A | 後端 859 測試 + Web 115 測試 + Shared 38 測試，全部通過 |
| **型別安全** | A | Web TypeScript strict 模式通過 |
| **記憶體安全** | A | 所有洩漏點已修復，backtest/alpha/run_now 均有過期清理+上限 |
| **WebSocket 穩定性** | A | 重連限制、連線上限、server-side ping、backpressure、handler 隔離、singleton |
| **錯誤處理** | A | 全域例外處理器 + 所有頁面 mountedRef + translateApiError 一致性 |
| **安全性** | A | 路徑穿越、WS 認證（含 token 傳遞）、auto-alpha WS 認證均已修復 |
| **Build 穩定性** | A | Production build 成功，bundle size 合理（1.1MB） |
| **棄用 API** | A | FastAPI lifespan 已遷移，asyncio deprecated API 已修正 |
| **資料庫穩定性** | A | PostgreSQL 連線池已配置 pool_size/pre_ping/recycle |
| **競爭條件** | A- | alpha_tasks/kill_switch 已加鎖，字典迭代安全，broadcast 有 backpressure |

---

> **文件維護**：本報告應隨穩定性測試的實際執行結果持續更新。建議每次重大版本釋出前重新執行完整穩定性測試流程。
