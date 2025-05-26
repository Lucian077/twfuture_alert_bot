from datetime import datetime, timedelta
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

# Flask 應用
app = Flask(__name__)

@app.route('/')
def home():
    return '布林通道監控服務運行中'

# Yahoo 台指期近月一 1 分 K 線資料
YAHOO_URL = 'https://tw.stock.yahoo.com/_td-stock/api/resource/FinanceChartService.apis;fields=chart;symbol=WTX%26.F?type=1m&range=1d'

def fetch_data():
    try:
        res = requests.get(YAHOO_URL, headers={'User-Agent': 'Mozilla/5.0'})
        res.raise_for_status()
        data = res.json()
        timestamps = data['chart']['timestamp']
        prices = data['chart']['indicators']['quote'][0]['close']
        df = pd.DataFrame({
            'datetime': pd.to_datetime(timestamps, unit='s') + timedelta(hours=8),
            'close': prices
        }).dropna()
        return df
    except Exception as e:
        print(f'❌ 發生錯誤：{e}')
        return pd.DataFrame()

def calculate_bollinger(df, period=20):
    df['MA'] = df['close'].rolling(window=period).mean()
    df['STD'] = df['close'].rolling(window=period).std()
    df['Upper'] = df['MA'] + 2 * df['STD']
    df['Lower'] = df['MA'] - 2 * df['STD']
    return df

last_notified_time = None

def monitor_bollinger():
    global last_notified_time
    df = fetch_data()
    if df.empty or len(df) < 20:
        return

    df = calculate_bollinger(df)
    latest = df.iloc[-1]
    price = latest['close']
    upper = latest['Upper']
    lower = latest['Lower']

    now = datetime.now()
    time_diff = (now - last_notified_time).total_seconds() if last_notified_time else None

    if price >= upper or price <= lower:
        if time_diff is None or time_diff >= 5:
            message = (
                f'📈 台指期突破布林通道\n'
                f'時間：{latest["datetime"]}\n'
                f'價格：{price:.2f}\n'
                f'上緣：{upper:.2f}\n'
                f'下緣：{lower:.2f}'
            )
            bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
            last_notified_time = now

# 背景監控
def run_monitoring_loop():
    while True:
        monitor_bollinger()
        time.sleep(5)

if __name__ == '__main__':
    import threading
    threading.Thread(target=run_monitoring_loop, daemon=True).start()
    app.run(host='0.0.0.0', port=10000)
