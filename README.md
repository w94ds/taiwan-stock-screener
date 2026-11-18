# TW TERMINAL V7 — 雙模式互動 K 線

## 升級方式
將 `app.py` 上傳至原 GitHub Repository 根目錄，覆蓋同名檔案並 Commit。原本的 `update_data.py`、`requirements.txt`、`.github/workflows/update.yml`、`data/`、`.streamlit/config.toml` 全部保留。Streamlit Cloud 會自動部署。

## 功能
- 條件選股與自選股兩種模式，最多六檔；選股結果採用全市場選股頁籤的目前條件。
- 聚焦主圖與六宮格切換，按股票按鈕放大；六宮格也可點「放大此股票」。
- Plotly 滾輪縮放、拖曳平移、十字游標及 OHLC 懸浮資訊。
- 成交量、RSI、MACD 整合於同一分析區。
- 沿用 V6 `data/history.csv.gz`，不會在訪客操作時下載行情。

## 限制
- 自選股在同一個 Streamlit 工作階段保留，**尚未實作跨重啟的瀏覽器永久儲存**；不同訪客互不共用。
- K 線使用 Plotly，並非 TradingView Lightweight Charts；提供縮放與拖曳，但沒有畫線工具。
- 歷史價格可能為調整後價格，與官方快照的收盤價存在差異。
- 尚未在你的實際 Streamlit Cloud 環境驗證。
