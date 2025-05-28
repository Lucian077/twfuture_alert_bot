from flask import Flask
import threading
import time
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz

# Telegram 設定
TELEGRAM_TOKEN = '7863895518:AAH0avbUgC_yd7RoImzBvQJXFmIrKXjuSj8'
CHAT_ID = '1190387445'

# 時區設定
tz = pytz.timezone("Asia/Taipei")

# 全域狀態變數
status_message = "初始化中"
last_update = "無數據"
last_price = "無"

# 建立 Flask App
app = Flask(__name__)

@app.route("/")
def index():
    return f"""
    <h2>台指期布林通道監控系統</h2>
    狀態：{status_message}<br>
    最後更新時間：{last_update}<br>
    最後價格：{last_price}
    """

# 發送 Telegram 訊息
def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message}
    try:
        response = requests.post(url, data=data)
        if response.status_code != 200:
            print(f"[{datetime.now(tz).strftime('%H:%M:%S')}] Telegram 傳送失敗: {response.text}")
    except Exception as e:
        print(f"[{datetime.now(tz).strftime('%H:%M:%S')}] Telegram 發送錯誤: {e}")

# 抓取 Yahoo 奇摩「台指期近月一」1分K線
def fetch_yahoo_futures():
    url = "https://tw.stock.yahoo.com/futures/real/MTX?col=last_trade&order=desc"  # 小型台指期替代網址，若抓不到可改 TXF
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    try:
        response = requests.get(url, headers=headers)
        dfs = pd.read_html(response.text)
        for df in dfs:
            if "成交價" in df.columns:
                price = float(df.iloc[0]["成交價"])
                return datetime.now(tz), price
    except Exception as e:
        print(f"[{datetime.now(tz).strftime('%H:%M:%S')}] 無法取得價格: {e}")
    return None, None

# 布林通道計算與通知邏輯
def monitor():
    global status_message, last_update, last_price
    history = []

    while True:
        now, price = fetch_yahoo_futures()
        if price:
            history.append(price)
            if len(history) > 100:
                history.pop(0)

            df = pd.Series(history)
            ma = df.rolling(20).mean().iloc[-1]
            std = df.rolling(20).std().iloc[-1]
            upper = ma + 2 * std
            lower = ma - 2 * std

            last_update = now.strftime("%Y-%m-%d %H:%M:%S")
            last_price = price
            status_message = "執行中"

            print(f"[{now.strftime('%H:%M:%S')}] 價格: {price}, 上緣: {round(upper)}, 下緣: {round(lower)}")

            if price > upper:
                send_telegram_message(f"📈 價格突破上緣！\n目前價格：{price}\n上緣：{round(upper)}")
            elif price < lower:
                send_telegram_message(f"📉 價格跌破下緣！\n目前價格：{price}\n下緣：{round(lower)}")

        else:
            status_message = "資料讀取失敗"
            print(f"[{datetime.now(tz).strftime('%H:%M:%S')}] 無法取得價格資料")

        time.sleep(10)

# 背景執行監控任務
def start_monitor_thread():
    thread = threading.Thread(target=monitor)
    thread.daemon = True
    thread.start()

if __name__ == "__main__":
    start_monitor_thread()
    app.run(host="0.0.0.0", port=10000)
