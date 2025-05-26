import pandas as pd
import numpy as np
import requests
from datetime import datetime
import time
import os
from flask import Flask

# Telegram 設定
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }
    requests.post(url, data=data)

# Yahoo 奇摩台指期即時資料
def get_realtime_txf_data():
    url = "https://tw.stock.yahoo.com/future/futures-intraday/TXF%3DF?sid=TXF%3DF"
    res = requests.get(url)
    dfs = pd.read_html(res.text)
    
    for df in dfs:
        if "時間" in df.columns and "成交" in df.columns:
            df = df.rename(columns={"時間": "time", "成交": "close"})
            df["time"] = pd.to_datetime(df["time"])
            df["close"] = pd.to_numeric(df["close"], errors="coerce")
            df = df.dropna(subset=["close"])
            return df[["time", "close"]]
    
    raise Exception("找不到符合的資料表")

# 計算布林通道
def compute_bollinger_bands(df, period=20, stdev=2):
    df["ma"] = df["close"].rolling(period).mean()
    df["std"] = df["close"].rolling(period).std()
    df["upper"] = df["ma"] + stdev * df["std"]
    df["lower"] = df["ma"] - stdev * df["std"]
    return df

# Flask 網頁應用保持服務活躍
app = Flask(__name__)

@app.route("/")
def home():
    return "✅ 台指期布林通道監控運作中"

@app.route("/ping")
def ping():
    return "✅ pong"

# 主程式：監控布林通道突破
def monitor():
    notified = False
    while True:
        try:
            df = get_realtime_txf_data()
            df = compute_bollinger_bands(df)
            latest = df.iloc[-1]
            price = latest["close"]
            upper = latest["upper"]
            lower = latest["lower"]

            if price >= upper and not notified:
                msg = f"📈 台指期價格突破布林通道【上軌】\n現在價格：{price}\n上軌：{upper}"
                send_telegram_message(msg)
                notified = True
            elif price <= lower and not notified:
                msg = f"📉 台指期價格突破布林通道【下軌】\n現在價格：{price}\n下軌：{lower}"
                send_telegram_message(msg)
                notified = True
            elif lower < price < upper:
                notified = False

        except Exception as e:
            print(f"錯誤：{e}")
        
        time.sleep(5)

if __name__ == "__main__":
    from threading import Thread
    Thread(target=monitor).start()
    app.run(host="0.0.0.0", port=10000)
