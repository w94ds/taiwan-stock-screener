"""Scheduled data build. No user-triggered scraping on public Streamlit instances."""
import datetime as dt
import json
import os
import time
from pathlib import Path
import numpy as np
import pandas as pd
import requests
import yfinance as yf

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'data'
OUT.mkdir(exist_ok=True)
SESSION = requests.Session()
SESSION.headers.update({'User-Agent': 'Mozilla/5.0 (compatible; StockScreenerResearch/4.0)'})

def num(v):
    try:
        s = str(v).replace(',', '').replace('+', '').strip()
        if s in ('', '--', '---', 'N/A', 'nan'): return np.nan
        return float(s)
    except (ValueError, TypeError): return np.nan

def official_prices():
    stocks = {}
    sources = []
    try:
        r = SESSION.get('https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL', timeout=35)
        r.raise_for_status()
        for item in r.json():
            s = str(item.get('Code','')).strip()
            if len(s) == 4 and s.isdigit() and num(item.get('ClosingPrice')) > 0:
                stocks[s] = {'symbol':s,'name':str(item.get('Name','')),'market':'上市', 'official_close':num(item.get('ClosingPrice'))}
        sources.append('TWSE STOCK_DAY_ALL')
    except Exception as e: print('TWSE price warning:', e, flush=True)
    try:
        r = SESSION.get('https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes',timeout=35)
        r.raise_for_status()
        for item in r.json():
            s = str(item.get('SecuritiesCompanyCode') or item.get('SecuritiesCode') or item.get('股票代號') or item.get('代號') or '').strip()
            p = num(item.get('Close') or item.get('收盤') or item.get('收盤價'))
            if len(s)==4 and s.isdigit() and p > 0:
                stocks[s] = {'symbol':s,'name':str(item.get('CompanyName') or item.get('Name') or item.get('股票名稱') or ''),'market':'上櫃','official_close':p}
        sources.append('TPEx daily quotes')
    except Exception as e: print('TPEx price warning:', e, flush=True)
    if not stocks: raise RuntimeError('No official symbols returned; keep previous published snapshot')
    return stocks, sources

def inst_twse(day):
    r=SESSION.get('https://www.twse.com.tw/rwd/zh/fund/T86',params={'response':'json','date':day.strftime('%Y%m%d'),'selectType':'ALLBUT0999'},timeout=35)
    r.raise_for_status(); payload=r.json(); fields=[str(x).replace(' ','') for x in payload.get('fields',[])]
    def field(*parts):
        return next((i for i,f in enumerate(fields) if all(x in f for x in parts)),None)
    si=field('證券代號');ti=field('投信','買賣超');fi=field('外陸資','買賣超')
    if si is None or ti is None: return {}
    out={}
    for row in payload.get('data',[]):
        symbol=str(row[si]).strip()
        if len(symbol)==4 and symbol.isdigit():
            out[symbol]={'trust_lots':num(row[ti])/1000,'foreign_lots':num(row[fi])/1000 if fi is not None else np.nan}
    return out

def get_institutions():
    today=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date()
    for offset in range(0,8):
        day=today-dt.timedelta(days=offset)
        if day.weekday()>=5:continue
        try:
            result=inst_twse(day)
            if result:return result,day.isoformat()
        except Exception as e: print('Institution warning',day,e,flush=True)
    return {},None

def extract_one(frame, ticker):
    if frame is None or frame.empty:return None
    try:
        d=frame[ticker] if isinstance(frame.columns,pd.MultiIndex) and ticker in frame.columns.get_level_values(0) else frame
        if isinstance(d.columns,pd.MultiIndex):
            d=d.droplevel(-1,axis=1) if len(set(d.columns.get_level_values(-1)))==1 else d
        d=d.dropna(subset=['Close']).sort_index()
        if len(d)<65:return None
        c=d['Close'].astype(float)
        delta=c.diff();up=delta.clip(lower=0).ewm(alpha=1/14,adjust=False).mean();down=(-delta.clip(upper=0)).ewm(alpha=1/14,adjust=False).mean()
        rsi=100-100/(1+up/down.replace(0,np.nan));rsi=rsi.mask((down==0)&(up>0),100)
        ema12=c.ewm(span=12,adjust=False).mean();ema26=c.ewm(span=26,adjust=False).mean();macd=ema12-ema26;signal=macd.ewm(span=9,adjust=False).mean()
        last=d.iloc[-1]
        return {'technical_day':pd.Timestamp(d.index[-1]).strftime('%Y-%m-%d'), 'close':float(last['Close']), 'volume':float(last['Volume']), 'ma5':float(c.rolling(5).mean().iloc[-1]),'ma10':float(c.rolling(10).mean().iloc[-1]),'ma20':float(c.rolling(20).mean().iloc[-1]),'ma60':float(c.rolling(60).mean().iloc[-1]),'rsi':float(rsi.iloc[-1]),'rsi_prev':float(rsi.iloc[-2]),'macd':float(macd.iloc[-1]),'signal':float(signal.iloc[-1])}
    except Exception as e:
        print('Ticker extraction warning',ticker,e,flush=True)
        return None

def run():
    stocks,sources=official_prices()
    institutions,inst_day=get_institutions()
    symbols=list(stocks)
    records=[];failed=[];history_parts=[]
    # Small batches keep memory manageable; rate limiting may still cause partial coverage.
    for start in range(0,len(symbols),40):
        batch=symbols[start:start+40]
        tickers=[s+('.TWO' if stocks[s]['market']=='上櫃' else '.TW') for s in batch]
        try:
            frame=yf.download(tickers,period='1y',auto_adjust=True,progress=False,threads=True,group_by='ticker',timeout=25)
            for s,t in zip(batch,tickers):
                data=extract_one(frame,t)
                if data:
                    records.append({**stocks[s],**data,**institutions.get(s,{}),'institution_day':inst_day if s in institutions else None})
                    try:
                        h=frame[t] if isinstance(frame.columns,pd.MultiIndex) else frame
                        h=h[['Open','High','Low','Close','Volume']].dropna(subset=['Close']).copy()
                        h.columns=['open','high','low','close','volume']
                        h=h.reset_index()
                        h=h.rename(columns={h.columns[0]:'date'})
                        h['date']=pd.to_datetime(h['date']).dt.strftime('%Y-%m-%d')
                        h['symbol']=s
                        history_parts.append(h[['symbol','date','open','high','low','close','volume']])
                    except Exception as he:
                        print('History extraction warning',s,he,flush=True)
                else:failed.append(s)
        except Exception as e:
            print('Batch warning',start,e,flush=True);failed.extend(batch)
        print(f'Processed {min(start+40,len(symbols))}/{len(symbols)}, success={len(records)}',flush=True)
        time.sleep(1.2)
    if len(records)<max(100,int(len(symbols)*0.50)):
        raise RuntimeError(f'Coverage too low: {len(records)}/{len(symbols)}; previous snapshot preserved')
    data=pd.DataFrame(records)
    data=data.replace([np.inf,-np.inf],np.nan)
    temp=OUT/'snapshot.tmp.gz'
    data.to_csv(temp,index=False,compression='gzip')
    os.replace(temp,OUT/'snapshot.csv.gz')
    if history_parts:
        history=pd.concat(history_parts,ignore_index=True)
        history=history.drop_duplicates(['symbol','date']).sort_values(['symbol','date'])
        htemp=OUT/'history.tmp.gz'
        history.to_csv(htemp,index=False,compression='gzip')
        os.replace(htemp,OUT/'history.csv.gz')
        print(f'Historical candles: {len(history)} rows, {history.symbol.nunique()} symbols',flush=True)
    metadata={'updated_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'symbols_official':len(symbols),'symbols_with_indicators':len(data),'symbols_failed':len(failed),'failed_sample':failed[:25],'institution_day':inst_day,'sources':sources+['Yahoo Finance historical adjusted prices','TWSE T86 institutional flow'],'notes':'Official quote API may show the prior trading session. Technical values and official close may use different adjustment bases; institution flow is TWSE only. Missing values are not zero.'}
    (OUT/'metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    print(metadata,flush=True)

if __name__=='__main__':run()
