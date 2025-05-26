import time
import requests
import pandas as pd
import numpy as np
from flask import Flask
import threading

# Telegram Bot 設定
TELEGRAM_TOKEN = '你的 Bot Token'
TELEGRAM_CHAT_ID = '你的 Chat ID'

# Yahoo Finance 台指期網址（近月合約）
YAHOO_URL = 'https://tw.stock.yahoo.com/future/q/txf/'

# 建立 Flask app
app = Flask(__name__)

# 傳送 Telegram 通知
def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }
    try:
        requests.post(url, data=data)
    except Exception as e:
        print(f"發送失敗：{e}")

# 取得即時價格
def get_realtime_price():
    try:
        tables = pd.read_html(YAHOO_URL, flavor='html5lib')
        price_table = tables[2]  # 第三個表格通常是報價
        price = float(price_table.iloc[0, 1].replace(',', ''))
        return price
    except Exception as e:
        print(f"❌ 發生錯誤：{e}")
        return None

# 模擬 1 分鐘 K 線資料（實務上應替換為真實歷史 1 分鐘線資料來源）
price_list = []

# 每 5 秒檢查突破
def monitor_bollinger():
    while True:
        price = get_realtime_price()
        if price is not None:
            price_list.append(price)
            if len(price_list) > 20:
                price_list.pop(0)

            if len(price_list) >= 20:
                series = pd.Series(price_list)
                ma = series.rolling(window=20).mean().iloc[-1]
                std = series.rolling(window=20).std().iloc[-1]
                upper = ma + 2 * std
                lower = ma - 2 * std

                print(f"目前價格: {price}, 上軌: {upper}, 下軌: {lower}")
                if price > upper:
                    send_telegram_message(f"🚀 台指期突破上軌！價格：{price}")
                elif price < lower:
                    send_telegram_message(f"📉 台指期跌破下軌！價格：{price}")
        time.sleep(5)

# Ping route for Render
@app.route("/ping")
def ping():
    return "pong", 200

# 啟動背景監控執行緒
def start_monitoring():
    threading.Thread(target=monitor_bollinger, daemon=True).start()

if __name__ == "__main__":
    start_monitoring()
    app.run(host="0.0.0.0", port=10000)
