import requests
import pandas as pd
import numpy as np
import time
import telegram
from flask import Flask

# Telegram 設定
TELEGRAM_TOKEN = '7863895518:AAH0avbUgC_yd7RoImzBvQJXFmIrKXjuSj8'
TELEGRAM_CHAT_ID = '1190387445'
bot = telegram.Bot(token=TELEGRAM_TOKEN)

# 建立 Flask App
app = Flask(__name__)

@app.route('/')
def home():
    return 'OK'  # 用於 keep-alive 機制

# Yahoo 台指期近月一 URL
YAHOO_URL = 'https://tw.stock.yahoo.com/future/q/ta?sid=WTX%26&date=&type=1'

# 儲存布林通道判斷狀態
notified_upper = False
notified_lower = False

def fetch_1min_k():
    try:
        res = requests.get(YAHOO_URL, timeout=10)
        tables = pd.read_html(res.text, flavor='html5lib')
        df = tables[3].copy()
        df.columns = ['時間', '成交價', '漲跌', '單量', '總量']
        df = df[df['時間'].str.contains(':')]
        df['時間'] = pd.to_datetime(df['時間'])
        df['成交價'] = pd.to_numeric(df['成交價'], errors='coerce')
        df = df.dropna()
        df = df.sort_values('時間')
        df = df.reset_index(drop=True)
        return df
    except Exception as e:
        print(f'❌ 發生錯誤：{e}')
        return None

def calculate_bollinger(df):
    df['MA'] = df['成交價'].rolling(window=20).mean()
    df['STD'] = df['成交價'].rolling(window=20).std()
    df['Upper'] = df['MA'] + 2 * df['STD']
    df['Lower'] = df['MA'] - 2 * df['STD']
    return df

def check_breakout(df):
    global notified_upper, notified_lower
    latest = df.iloc[-1]
    price = latest['成交價']
    upper = latest['Upper']
    lower = latest['Lower']

    if price > upper:
        if not notified_upper:
            bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f'🚀 台指期突破布林通道上緣！價格：{price}')
            notified_upper = True
            notified_lower = False
    elif price < lower:
        if not notified_lower:
            bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f'🔻 台指期跌破布林通道下緣！價格：{price}')
            notified_lower = True
            notified_upper = False
    else:
        notified_upper = False
        notified_lower = False

# 每 5 秒監控一次布林通道
def monitor():
    while True:
        df = fetch_1min_k()
        if df is not None and len(df) >= 20:
            df = calculate_bollinger(df)
            check_breakout(df)
        time.sleep(5)

if __name__ == '__main__':
    import threading
    threading.Thread(target=monitor, daemon=True).start()
    app.run(host='0.0.0.0', port=10000)
