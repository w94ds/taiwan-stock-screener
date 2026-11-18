# 台股選股工作台 V4 — Streamlit Community Cloud 公開部署

本版從 V3 的 Flask + SQLite + 本機 APScheduler 架構改為 **Streamlit 網頁 + GitHub Actions 定時產生 CSV 快照**。Streamlit Community Cloud 可能休眠、重啟，不能依賴站內排程或持久 SQLite；因此訪客只能讀取 GitHub Repo 內最新的快照，不會觸發大量抓取。

## 1. 免費部署步驟

1. 建立 GitHub 帳號，建立一個 **Public** Repository，例如 `taiwan-stock-screener`。
2. 解壓縮本 ZIP，將**資料夾內所有檔案（包含 `.github` 與 `.streamlit` 隱藏資料夾）**上傳到 Repository 根目錄。不要只上傳 ZIP。GitHub 網頁上傳可能看不到隱藏資料夾，建議使用 GitHub Desktop 或 `git add -A`。
3. Repository → **Settings → Actions → General → Workflow permissions**，選 **Read and write permissions**，儲存。這讓每日排程可以提交更新後的快照。僅對可信任的 repository 開啟此權限。
4. Repository → **Actions → Update Taiwan stock snapshot → Run workflow**，先手動跑第一次資料更新。等工作流程成功並提交 `data/snapshot.csv.gz` 與 `data/metadata.json`。第一次可能需要數十分鐘；Yahoo 限流或官方資料異常可能導致失敗，請看 Actions log。
5. 前往 https://share.streamlit.io/ ，用 GitHub 登入，按 **Create app / Deploy**，選擇剛剛的 Repository、分支 `main`、入口 `app.py`，按 Deploy。
6. 等待部署完成，得到 `https://你的-app-name.streamlit.app` 公開網址，任何人都能存取。
7. 若 GitHub Actions 提交新快照，Streamlit Community Cloud 通常會重新部署或同步 GitHub 檔案；若畫面仍舊，稍後刷新並確認檔案版本。

## 2. 排程與資料

`.github/workflows/daily-update.yml` 設定為台灣時間週一到週五 **17:30**（UTC 09:30）執行。GitHub 排程可能延遲或略過；免費服務不提供 SLA。也可以在 Actions 手動觸發。

資料流程：TWSE / TPEx 官方每日快照取得股票清單 → Yahoo Finance 批次歷史價格計算 MA5/10/20/60、RSI(14)、MACD → TWSE T86 投信 / 外資買賣超 → `data/snapshot.csv.gz`。**不會把缺失的投信資料當成零**。技術日期是 Yahoo 歷史價格的實際最後日期，官方股票清單可能來自前一交易日。若取得有效資料低於 50% 或少於 100 檔，更新失敗並保留上次快照；若高於門檻但仍部分失敗，頁面會顯示覆蓋率。

## 3. 目前功能與限制

- 可公開瀏覽：全市場 MA20、RSI 轉強、MACD、上市投信買超、價格區間、上市/上櫃、代號搜尋、CSV 匯出。
- 介面：寬版三欄、可捲動結果表格、個股技術指標摘要。
- **歷史回測尚未開放**：V3 的即時回測依賴訪客請求時下載行情，公開免費站容易限流。V4 先將回測頁籤保留為說明，不會假裝已有回測結果。後續可由 GitHub Actions 預先計算歷史策略績效後再開放。
- 上櫃投信買賣超尚未串接；勾選投信買超時，上櫃股票因無數據而被排除。
- Yahoo Finance 可能限制大量請求；免費 GitHub Actions 執行時間和資源有限，全市場更新不保證每次成功。
- 公開展示或商業使用前，請自行確認 TWSE、TPEx、Yahoo Finance 相關授權與再散布條款。

## 4. 本機測試

Python 3.11 建議：

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python update_data.py
streamlit run app.py
```

**安全**：公開版沒有更新 API、沒有訪客輸入的任意 SQL/命令、沒有管理員密碼。不要將 token、API Key 或 `.streamlit/secrets.toml` 提交到公開 Repository。
