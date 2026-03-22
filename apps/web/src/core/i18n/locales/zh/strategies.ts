export const strategies = {
  title: "策略管理",
  start: "啟動",
  stop: "停止",
  noStrategies: "尚未配置策略",
  strategyDescriptions: {
    momentum: "經典 12-1 動量策略。買入過去 12 個月漲幅最強的股票（跳過最近 1 個月以避免短期反轉）。依信號強度比例分配權重，單一標的上限 10%、總曝險上限 95%。每週或每月再平衡。",
    mean_reversion: "均值回歸策略。買入價格大幅偏離移動平均線下方（Z-score 超過閾值，預設 1.5）的股票。依信號加權配置，單一標的上限 8%、總曝險上限 90%。適合橫盤震盪、動量不明顯的市場環境。",
  },
};
