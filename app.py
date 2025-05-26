import time
import requests
import pandas as pd
import numpy as np
import telegram
from flask import Flask
from threading import Thread

# Telegram 設定
TELEGRAM_TOKEN = '7863895518:AAH0avbUgC_yd7RoImzBvQJXFmIrKXjuSj8'
TELEGRAM_CHAT_ID = '1190387445'
bot = telegram.Bot(token=TELEGRAM_TOKEN)

# Flask App
app = Flask(__name__)

@app.route('/')
def home():
    return 'OK'

# Yahoo 奇摩台指期近月一的網址
URL = "https://tw.stock.yahoo.com/future/charts.html?sid=WTX%26&type=1"

# 紀錄最後一次通知的時間
last_notified_time = None

def fetch_latest_1min_k():
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    res = requests.get(URL, headers=headers)
    tables = pd.read_html(res.text, flavor="html5lib")
    
    for table in tables:
        if table.shape[1] >= 6 and "時間" in table.columns:
            df = table.copy()
            df.columns = [col.strip() for col in df.columns]
            df = df[["時間", "成交"]]
            df.columns = ["Time", "Close"]
            df = df.dropna()
            df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
            df = df.dropna()
            df = df.iloc[::-1].reset_index(drop=True)  # 時間順序由舊到新
            return df
    raise Exception("❌ 無法從 Yahoo 擷取到台指期近月一資料")

def compute_bollinger_bands(df, period=20, num_std=2):
    df["MA"] = df["Close"].rolling(window=period).mean()
    df["STD"] = df["Close"].rolling(window=period).std()
    df["Upper"] = df["MA"] + num_std * df["STD"]
    df["Lower"] = df["MA"] - num_std * df["STD"]
    return df

def monitor():
    global last_notified_time
    print("📈 開始監控台指期布林通道突破狀況...")

    while True:
        try:
            df = fetch_latest_1min_k()
            if len(df) < 20:
                print("資料不足，等待更多資料填滿布林通道...")
                time.sleep(5)
                continue

            df = compute_bollinger_bands(df)
            latest = df.iloc[-1]

            close = latest["Close"]
            upper = latest["Upper"]
            lower = latest["Lower"]
            time_label = latest["Time"]

            # 每次都印出最新數據以方便除錯
            print(f"[{time_label}] Close: {close}, Upper: {upper}, Lower: {lower}")

            # 判斷是否突破
            if close > upper or close < lower:
                if last_notified_time != time_label:
                    message = f"⚠️ 台指期價格突破布林通道！\n時間：{time_label}\n價格：{close}\n上軌：{upper:.2f}\n下軌：{lower:.2f}"
                    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
                    last_notified_time = time_label
                    print("✅ 已發送通知")
            else:
                print("📊 價格在布林通道範圍內")

        except Exception as e:
            print(f"❌ 發生錯誤：{e}")

        time.sleep(5)

# 執行背景監控執行緒
def start_monitoring():
    monitor_thread = Thread(target=monitor)
    monitor_thread.daemon = True
    monitor_thread.start()

if __name__ == '__main__':
    start_monitoring()
    app.run(host='0.0.0.0', port=10000)
