"""Public read-only Taiwan stock screener. Data refresh happens in GitHub Actions."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT=Path(__file__).resolve().parent
st.set_page_config(page_title='台股選股工作台 V4',page_icon='📈',layout='wide',initial_sidebar_state='collapsed')
st.markdown('''<style>
.block-container {max-width:100%;padding:0.7rem 1.3rem 1.5rem}
h1 {font-size:1.55rem!important;margin:0!important}
[data-testid="stMetric"] {background:#162236;padding:8px 12px;border-radius:8px}
[data-testid="stMetricValue"] {font-size:1.25rem}
</style>''',unsafe_allow_html=True)

@st.cache_data(ttl=300,show_spinner=False)
def load_snapshot(mtime):
    path=ROOT/'data'/'snapshot.csv.gz'
    if not path.exists():return pd.DataFrame()
    df=pd.read_csv(path,dtype={'symbol':str})
    for key in ('close','ma5','ma10','ma20','ma60','rsi','rsi_prev','macd','signal','trust_lots','foreign_lots','volume'):
        if key in df:df[key]=pd.to_numeric(df[key],errors='coerce')
    return df

path=ROOT/'data'/'snapshot.csv.gz'
df=load_snapshot(path.stat().st_mtime if path.exists() else 0)
meta_path=ROOT/'data'/'metadata.json'
meta=json.loads(meta_path.read_text(encoding='utf-8')) if meta_path.exists() else {}
st.title('📈 台股選股工作台 V4')
st.caption('公開唯讀版 · 每日盤後由 GitHub Actions 批次更新 · 資料僅供研究，非投資建議')
if df.empty:
    st.warning('尚未產生市場資料。請先到 GitHub Repository → Actions → Update Taiwan stock snapshot → Run workflow，完成後刷新此頁。')
    st.info('第一次執行需要批次取得歷史行情，可能需要數十分鐘；若外部 API 限流，排程會保留上一份有效快照。')
    st.stop()

available=len(df)
tech_day=str(df['technical_day'].max()) if 'technical_day' in df else '未知'
inst_day=meta.get('institution_day') or '尚無'
a,b,c,d=st.columns(4)
a.metric('技術指標股票數',f'{available:,}')
b.metric('最新技術交易日',tech_day)
c.metric('上市投信資料日',inst_day)
d.metric('資料覆蓋率',f"{available/max(meta.get('symbols_official',available),1)*100:.1f}%")

screen_tab,backtest_tab,about_tab=st.tabs(['🔎 全市場篩選','📊 策略回測','ℹ️ 資料說明'])
with screen_tab:
    filters,results,detail=st.columns([1.12,3.2,2.0],gap='medium')
    with filters:
        st.subheader('篩選條件')
        market=st.selectbox('市場',['全部','上市','上櫃'])
        query=st.text_input('代號 / 名稱',placeholder='例如 2330')
        lo,hi=st.columns(2)
        min_price=lo.number_input('最低股價',min_value=0.0,value=0.0,step=5.0)
        max_price=hi.number_input('最高股價',min_value=0.0,value=0.0,step=5.0,help='0 表示不限')
        above=st.checkbox('股價站上 MA20',value=True)
        rising=st.checkbox('RSI(14) 轉強',value=True,help='最新 RSI 大於上一交易日 RSI')
        min_rsi=st.slider('最低 RSI',0,100,45)
        bull=st.checkbox('MACD 多頭 (DIF > DEA)',value=False)
        trust=st.checkbox('投信買超',value=True,help='僅上市有資料；無資料不視為 0')
        trust_min=st.number_input('投信最低買超（張）',value=0.0,step=100.0,disabled=not trust)
        fresh=st.checkbox('僅最新技術交易日',value=True)
    view=df.copy()
    if market!='全部':view=view[view.market==market]
    if query:view=view[view.symbol.str.contains(query,case=False,regex=False)|view.name.fillna('').str.contains(query,case=False,regex=False)]
    view=view[view.close>=min_price]
    if max_price>0:view=view[view.close<=max_price]
    if above:view=view[view.close>view.ma20]
    if rising:view=view[view.rsi>view.rsi_prev]
    view=view[view.rsi>=min_rsi]
    if bull:view=view[view.macd>view.signal]
    if trust:view=view[view.trust_lots>trust_min]
    if fresh:view=view[view.technical_day==tech_day]
    view=view.sort_values(['trust_lots','symbol'],ascending=[False,True],na_position='last')
    with results:
        st.subheader(f'篩選結果 · {len(view):,} 檔')
        if view.empty:st.info('沒有符合條件的股票。可取消投信條件、降低 RSI 門檻，或檢查資料日期。')
        cols=['symbol','name','market','technical_day','close','ma20','rsi','rsi_prev','macd','signal','trust_lots','foreign_lots']
        labels={'symbol':'代號','name':'名稱','market':'市場','technical_day':'日期','close':'收盤','ma20':'MA20','rsi':'RSI','rsi_prev':'前日 RSI','macd':'MACD','signal':'訊號線','trust_lots':'投信買超(張)','foreign_lots':'外資買超(張)'}
        st.dataframe(view[[x for x in cols if x in view]].rename(columns=labels),hide_index=True,use_container_width=True,height=540)
        st.download_button('⬇️ 匯出篩選結果 CSV',view.to_csv(index=False).encode('utf-8-sig'),'taiwan_stock_screen.csv','text/csv',disabled=view.empty)
    with detail:
        st.subheader('個股技術摘要')
        choices=view if not view.empty else df
        symbols=choices.symbol.astype(str).tolist()
        selected=st.selectbox('選擇股票',symbols,format_func=lambda s: f"{s} {str(choices.loc[choices.symbol==s,'name'].iloc[0])}")
        item=choices.loc[choices.symbol==selected].iloc[0]
        x,y=st.columns(2)
        x.metric('最新收盤',f"{item.close:.2f}")
        y.metric('MA20',f"{item.ma20:.2f}")
        x.metric('RSI(14)',f"{item.rsi:.1f}")
        y.metric('投信買超',f"{item.trust_lots:,.0f} 張" if pd.notna(item.get('trust_lots')) else '無資料')
        fig=go.Figure()
        fig.add_trace(go.Bar(x=['MA5','MA10','MA20','MA60','收盤'],y=[item.ma5,item.ma10,item.ma20,item.ma60,item.close],marker_color=['#64748b']*4+['#2dd4bf']))
        fig.update_layout(height=260,margin=dict(l=0,r=0,t=12,b=0),template='plotly_dark',showlegend=False,yaxis_title='價格')
        st.plotly_chart(fig,use_container_width=True)
        st.caption(f"技術日期：{item.technical_day}。右側為指標快照，非歷史 K 線。")

with backtest_tab:
    st.subheader('歷史策略回測（公開版）')
    st.info('此版本為安全的唯讀公開部署：不在訪客操作時呼叫 Yahoo Finance。全市場指標已可篩選；歷史逐筆回測需要另行預先計算回測資料集，避免公開站點因多人請求被限流。')
    st.write('目前可用條件：MA20、RSI、MACD 與投信買超；歷史回測功能暫未啟用，不會顯示虛構績效。')
with about_tab:
    st.subheader('資料與限制')
    st.json(meta)
    st.markdown('''- **技術價格**：Yahoo Finance 調整後歷史價格，依資料供應商可用性計算；與 TWSE/TPEx 官方未調整收盤價可能不同。\n- **投信買超**：TWSE T86 上市資料，單位由股轉換為張；上櫃未提供投信數據，篩選時會被排除。\n- **更新**：GitHub Actions 工作日 17:30（台北時間）嘗試更新；不保證在休市、API 異常或 GitHub 排程延遲時準時。\n- **公開資料**：若要公開或商業重發布，應自行確認資料來源的使用及授權條款。''')
