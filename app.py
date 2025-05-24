import pandas as pd
import numpy as np
import requests
import time
import os
from datetime import datetime
from flask import Flask

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }
    requests.post(url, data=data)

def fetch_txf_1min_data():
    url = "https://www.taifex.com.tw/cht/3/futDataDown"
    payload = {
        "down_type": "1",
        "commodity_id": "TXF",
        "queryStartDate": datetime.now().strftime("%Y/%m/%d"),
        "queryEndDate": datetime.now().strftime("%Y/%m/%d")
    }
    try:
        response = requests.post(url, data=payload)
        df = pd.read_html(response.text)[0]
        df.columns = df.columns.droplevel()
        df = df.rename(columns={"成交時間": "time", "成交價格": "close"})
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df = df.dropna(subset=["close"])
        return df[["time", "close"]].tail(20)
    except Exception as e:
        print("Fetch error:", e)
        return pd.DataFrame(columns=["time", "close"])

def compute_bollinger_bands(df, period=20, stddev=2):
    df['ma'] = df['close'].rolling(period).mean()
    df['std'] = df['close'].rolling(period).std()
    df['upper'] = df['ma'] + stddev * df['std']
    df['lower'] = df['ma'] - stddev * df['std']
    return df

def monitor():
    last_signal = None
    while True:
        df = fetch_txf_1min_data()
        if df.empty or len(df) < 20:
            time.sleep(5)
            continue

        df = compute_bollinger_bands(df)
        latest = df.iloc[-1]
        price = latest['close']
        upper = latest['upper']
        lower = latest['lower']

        message = f"📈 台指期 1分鐘布林通道監控\n時間：{datetime.now().strftime('%H:%M:%S')}\n價格：{price}"

        if price >= upper and last_signal != 'upper':
            message += "\n🚨 價格觸碰布林【上軌】"
            send_telegram_message(message)
            last_signal = 'upper'
        elif price <= lower and last_signal != 'lower':
            message += "\n🚨 價格觸碰布林【下軌】"
            send_telegram_message(message)
            last_signal = 'lower'
        elif lower < price < upper:
            last_signal = None

        time.sleep(5)

@app.route('/')
def index():
    return '📡 台指期布林通道監控機器人運作中...'

if __name__ == '__main__':
    import threading
    threading.Thread(target=monitor).start()
    app.run(host='0.0.0.0', port=10000)
