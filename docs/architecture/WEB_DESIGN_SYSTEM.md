# Web Design System — 視覺設計規範

> 版本：v1.0
> 日期：2026-03-27
> 參考：Linear、Vercel/Geist、Mercury Bank、Stripe、shadcn/ui、Tremor、TradingView
> 原則：Dark-mode-first、資料密度適中、台灣在地化（紅漲綠跌）

---

## 1. 配色系統（Dark-Mode-First）

### 背景層級（4 層）

```
Level 0（Sidebar）:     #0a0a0a   neutral-950    最深
Level 1（頁面）:        #111111   ≈ neutral-900   主背景
Level 2（卡片）:        #1a1a1a   ≈ neutral-850   內容面板
Level 3（浮層/hover）:  #262626   neutral-800     彈窗/hover
```

Tailwind 自定義：
```javascript
surface: {
  0: '#0a0a0a',   // sidebar
  1: '#111111',   // page
  2: '#1a1a1a',   // card
  3: '#262626',   // raised
}
```

### 語義色（台灣在地化）

| 語義 | 色值 | Tailwind | 說明 |
|------|------|---------|------|
| **漲/獲利** | `#ef4444` | `red-500` | 🔴 台灣慣例紅=漲 |
| 漲-背景 | `#7f1d1d` | `red-900` | 獲利行底色 |
| **跌/虧損** | `#10b981` | `emerald-500` | 🟢 台灣慣例綠=跌 |
| 跌-背景 | `#065f46` | `emerald-800` | 虧損行底色 |
| 風險-低 | `#10b981` | `emerald-500` | |
| 風險-中 | `#f59e0b` | `amber-500` | |
| 風險-高 | `#ef4444` | `red-500` | |
| 主操作 | `#3b82f6` | `blue-500` | CTA 按鈕 |
| 主操作-hover | `#2563eb` | `blue-600` | |

### 邊框

Dark mode 用 `border-white/10`（10% 透明白），不用實色邊框：
```
預設：     border-white/10
hover：    border-white/15
focus：    ring-1 ring-blue-500/50
active/選中：border-blue-500/50
```

### 文字

```
主文字：     text-neutral-50   (#fafafa)
次要文字：   text-neutral-400  (#a3a3a3)
禁用/提示：  text-neutral-500  (#737373)
```

---

## 2. 字型

### Font Stack

```css
--font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
--font-mono: 'JetBrains Mono', 'Geist Mono', 'SF Mono', monospace;
```

### 數字必用等寬

**所有金額、百分比、價格都加 `tabular-nums`**：

```html
<span class="tabular-nums">$1,234,567.89</span>
<span class="tabular-nums">+2.34%</span>
```

### 字級

| 用途 | 大小 | 字重 | Tailwind | 範例 |
|------|------|------|---------|------|
| 大數字（NAV） | 36px | 700 | `text-4xl font-bold` | $10,234,567 |
| 段落標題 | 20px | 600 | `text-xl font-semibold` | 持倉明細 |
| 卡片標題 | 16px | 600 | `text-base font-semibold` | Portfolio Value |
| 正文 | 14px | 400 | `text-sm` | 一般說明文字 |
| 標籤 | 14px | 500 | `text-sm font-medium` | 導航項、欄位名 |
| 輔助/時間 | 12px | 400 | `text-xs` | 更新: 2s 前 |
| 金融數據 | 13px | 500 | `text-[13px] font-medium font-mono` | 196.50 |

---

## 3. 間距節奏（8px 基準）

```
4px   (gap-1)    — icon 與文字的間距
8px   (gap-2)    — 行內元素間距
12px  (gap-3)    — 列表項之間
16px  (p-4)      — 卡片內距（緊湊）
20px  (p-5)      — 卡片內距（標準）
24px  (gap-6)    — 卡片之間
32px  (gap-8)    — 區塊之間
48px  (mt-12)    — 大區塊分隔
```

**空白比**：60% 內容 / 40% 空白。比一般 SaaS（50/50）緊湊，但不像 Bloomberg（80/20）那麼密。

---

## 4. 圓角

```
inputs/buttons/badges：  rounded-md   (6px)
cards/dropdowns：        rounded-lg   (8px)   ← 主圓角
modals/large panels：    rounded-xl   (12px)
pills/tags：             rounded-full (9999px)
```

**巢狀規則**：外層 `rounded-lg`，內層元素 `rounded-md`。

---

## 5. 陰影

Dark mode **不用陰影，用邊框**：

```
卡片：    ring-1 ring-white/10                     ← 取代 shadow
浮層：    ring-1 ring-white/8 shadow-xl shadow-black/50
focus：   ring-2 ring-blue-500/50
```

Light mode（如果支援）：
```
shadow-sm   — 一般卡片
shadow-md   — 浮層
shadow-lg   — modal
```

---

## 6. 卡片模板

### 標準資料卡

```html
<div class="rounded-lg border border-white/10 bg-[#1a1a1a] p-5">
  <p class="text-sm font-medium text-neutral-400">Portfolio Value</p>
  <p class="mt-1 text-3xl font-bold tabular-nums tracking-tight text-white">
    $1,234,567
  </p>
  <span class="mt-1 inline-flex items-center gap-1 text-xs text-red-400">
    ▲ +2.34%
  </span>
</div>
```

### 可互動卡片

```html
<div class="rounded-lg border border-white/10 bg-[#1a1a1a] p-5
            transition-colors duration-150 hover:bg-[#262626] hover:border-white/15
            cursor-pointer">
  ...
</div>
```

### 強調卡片（選中策略）

```html
<div class="rounded-lg border border-blue-500/50 bg-blue-500/5 p-5
            ring-1 ring-blue-500/20">
  ...
</div>
```

---

## 7. 表格

```html
<table class="w-full text-sm">
  <thead>
    <tr class="border-b border-white/10 text-left">
      <th class="pb-3 text-xs font-medium uppercase tracking-wider text-neutral-500">
        Symbol
      </th>
      <th class="pb-3 text-right text-xs font-medium uppercase tracking-wider text-neutral-500">
        Price
      </th>
    </tr>
  </thead>
  <tbody class="divide-y divide-white/5">
    <tr class="transition-colors duration-150 hover:bg-white/5">
      <td class="py-3 font-medium text-white">2330.TW</td>
      <td class="py-3 text-right font-mono text-[13px] tabular-nums text-white">
        $196.50
      </td>
      <td class="py-3 text-right font-mono text-[13px] tabular-nums text-red-400">
        ▲ +1.23%
      </td>
    </tr>
  </tbody>
</table>
```

- 行高：`py-3`（約 44px/行）
- 分隔：`divide-white/5`（極淡，幾乎看不見但有層次）
- 數字：`text-right tabular-nums font-mono`
- hover：`hover:bg-white/5`

---

## 8. Icon

```
風格：     Outline（Lucide Icons）
線寬：     1.5px
尺寸：     16px（行內）/ 20px（標準）/ 24px（突出）
顏色：     text-neutral-400（預設）/ text-white（active）/ text-blue-500（accent）
Active：  改用 filled 版本
```

---

## 9. 動畫

### 微互動

```
hover/focus:    duration-150 ease-out
dropdown/tab:   duration-200 ease-out
modal/page:     duration-220 ease-out
chart update:   duration-300 ease-in-out
```

### 即時數據閃爍（Trading 專用）

```css
@keyframes flash-profit {
  0% { background-color: rgba(239, 68, 68, 0.3); }  /* red for TW profit */
  100% { background-color: transparent; }
}
@keyframes flash-loss {
  0% { background-color: rgba(16, 185, 129, 0.3); }  /* green for TW loss */
  100% { background-color: transparent; }
}
```

duration: 0.6s。WebSocket 更新價格時觸發。

### LiveDot 脈動

```css
@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
.live-dot {
  width: 8px; height: 8px; border-radius: 50%;
  animation: pulse-dot 2s ease-in-out infinite;
}
.live-dot-connected { background: #10b981; }
.live-dot-delayed   { background: #f59e0b; }
.live-dot-disconnected { background: #ef4444; animation: none; }
```

---

## 10. 圖表

```javascript
const chartTheme = {
  gridColor: 'rgba(255,255,255,0.06)',
  axisLabelColor: '#737373',         // neutral-500
  axisFontSize: 11,

  lineColor: '#3b82f6',              // blue-500
  lineWidth: 2,
  areaTopColor: 'rgba(59,130,246,0.3)',
  areaBottomColor: 'rgba(59,130,246,0)',

  tooltipBg: '#1a1a1a',
  tooltipBorder: 'rgba(255,255,255,0.10)',
  tooltipRadius: 8,

  seriesPalette: ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899'],
};
```

---

## 11. 不做的事

| 避免 | 原因 | 替代 |
|------|------|------|
| Glassmorphism blur 背景 | 2026 衰退趨勢、影響數據可讀性 | 實色背景 + border |
| Neumorphism 軟陰影 | 無障礙失敗、已死趨勢 | Flat + border |
| 純 #00FF00 / #FF0000 | WCAG 不通過 | emerald-500 / red-500 |
| 卡片多色漸層 | 視覺雜訊 | 最多 1 個 accent 漸層按鈕 |
| Dark mode 用 box-shadow | 看不見、浪費 | `ring-1 ring-white/10` |
| 比例數字（非等寬） | 表格欄位不對齊 | `tabular-nums` |
| > 300ms 動畫 | 交易情境下感覺遲鈍 | 150ms hover、200ms 轉場 |
| 裝飾性動畫 | 干擾數據判讀 | 只做狀態回饋動畫 |

---

## 12. Tailwind Config

```javascript
/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Geist Mono', 'SF Mono', monospace'],
      },
      colors: {
        surface: {
          0: '#0a0a0a',
          1: '#111111',
          2: '#1a1a1a',
          3: '#262626',
        },
        profit: { DEFAULT: '#ef4444', soft: '#7f1d1d' },   // 台灣：紅=漲
        loss:   { DEFAULT: '#10b981', soft: '#065f46' },    // 台灣：綠=跌
      },
      borderRadius: { card: '8px' },
      fontSize: {
        data: ['13px', { lineHeight: '20px', fontWeight: '500' }],
      },
      keyframes: {
        'flash-profit': {
          '0%': { backgroundColor: 'rgba(239,68,68,0.3)' },
          '100%': { backgroundColor: 'transparent' },
        },
        'flash-loss': {
          '0%': { backgroundColor: 'rgba(16,185,129,0.3)' },
          '100%': { backgroundColor: 'transparent' },
        },
        'pulse-dot': {
          '0%,100%': { opacity: '1' },
          '50%': { opacity: '0.4' },
        },
      },
      animation: {
        'flash-profit': 'flash-profit 0.6s ease-out',
        'flash-loss': 'flash-loss 0.6s ease-out',
        'pulse-dot': 'pulse-dot 2s ease-in-out infinite',
      },
    },
  },
};
```
