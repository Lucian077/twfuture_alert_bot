import os
import time
import requests
import pandas as pd
import numpy as np
from datetime import datetime
from flask import Flask

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

last_status = None  # 記錄上次的狀態（避免重複通知）

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }
    requests.post(url, data=data)

def get_simulated_txf_data():
    url = "https://www.taifex.com.tw/cht/3/futDataDown"
    date_str = datetime.now().strftime("%Y/%m/%d")
    payload = {
        'down_type': '1',
        'commodity_id': 'TXF',
        'queryStartDate': date_str,
        'queryEndDate': date_str
    }
    res = requests.post(url, data=payload)
    df = pd.read_html(res.text)[0]
    df.columns = df.columns.droplevel(0)
    df = df.rename(columns={'成交時間': 'time', '成交價格': 'price'})
    df['price'] = pd.to_numeric(df['price'], errors='coerce')
    df = df.dropna()
    df['time'] = pd.to_datetime(df['time'])
    df = df.sort_values('time')
    df = df.resample('1min', on='time').last().dropna()
    df = df.reset_index()
    df = df[['time', 'price']]
    df.columns = ['time', 'close']
    return df

def compute_bollinger_bands(df, period=20, stdev=2):
    df['ma'] = df['close'].rolling(period).mean()
    df['std'] = df['close'].rolling(period).std()
    df['upper'] = df['ma'] + stdev * df['std']
    df['lower'] = df['ma'] - stdev * df['std']
    return df

def check_and_notify():
    global last_status
    try:
        df = get_simulated_txf_data()
        df = compute_bollinger_bands(df)
        latest = df.iloc[-1]
        price = latest['close']
        upper = latest['upper']
        lower = latest['lower']
        time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if price >= upper and last_status != 'above':
            message = f"📈 台指期突破布林上軌！\n時間：{time_str}\n價格：{price:.2f}"
            send_telegram_message(message)
            last_status = 'above'
        elif price <= lower and last_status != 'below':
            message = f"📉 台指期跌破布林下軌！\n時間：{time_str}\n價格：{price:.2f}"
            send_telegram_message(message)
            last_status = 'below'
        elif lower < price < upper:
            last_status = 'inside'
    except Exception as e:
        print("錯誤：", e)

@app.route('/ping')
def ping():
    return "✅ I'm alive"

if __name__ == "__main__":
    while True:
        check_and_notify()
        time.sleep(5)
