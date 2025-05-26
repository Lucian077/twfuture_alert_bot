import requests
import pandas as pd
import numpy as np
import time
import telegram
import threading
from flask import Flask
from datetime import datetime

# === 你的 Telegram Bot 設定 ===
TELEGRAM_TOKEN = '7863895518:AAH0avbUgC_yd7RoImzBvQJXFmIrKXjuSj8'
TELEGRAM_CHAT_ID = '1190387445'
bot = telegram.Bot(token=TELEGRAM_TOKEN)

# === 建立 Flask Web App ===
app = Flask(__name__)

@app.route('/')
def index():
    return '台指期布林通道監控機器人運行中'

# === 抓取 Yahoo 台指期資料 ===
def get_txf_data():
    try:
        url = "https://tw.stock.yahoo.com/futures/real-time/MTX%26"
        res = requests.get(url)
        tables = pd.read_html(res.text, flavor='html5lib')
        df = tables[1]  # 第2張表通常是即時行情表
        df.columns = df.columns.droplevel() if isinstance(df.columns, pd.MultiIndex) else df.columns
        df = df[['時間', '成交價']]
        df = df.rename(columns={'成交價': 'price', '時間': 'time'})
        df = df.dropna()
        df['price'] = pd.to_numeric(df['price'], errors='coerce')
        df['time'] = pd.to_datetime(df['time'])
        df = df.dropna()
        return df.tail(20)
    except Exception as e:
        print(f"❌ 發生錯誤：{e}")
        return None

# === 計算布林通道 ===
def calculate_bollinger_bands(df):
    df['MA20'] = df['price'].rolling(window=20).mean()
    df['STD'] = df['price'].rolling(window=20).std()
    df['Upper'] = df['MA20'] + 2 * df['STD']
    df['Lower'] = df['MA20'] - 2 * df['STD']
    return df

# === 發送 Telegram 訊息 ===
def send_telegram_message(message):
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except Exception as e:
        print(f"❌ Telegram 發送錯誤：{e}")

# === 判斷是否突破上下緣 ===
last_status = ""

def monitor_job():
    global last_status
    while True:
        df = get_txf_data()
        if df is not None and len(df) >= 20:
            df = calculate_bollinger_bands(df)
            latest = df.iloc[-1]
            price = latest['price']
            upper = latest['Upper']
            lower = latest['Lower']
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            if price > upper:
                if last_status != 'above':
                    send_telegram_message(f"📈 台指期突破布林通道上緣！\n時間：{now}\n價格：{price:.2f} > 上緣：{upper:.2f}")
                    last_status = 'above'
            elif price < lower:
                if last_status != 'below':
                    send_telegram_message(f"📉 台指期跌破布林通道下緣！\n時間：{now}\n價格：{price:.2f} < 下緣：{lower:.2f}")
                    last_status = 'below'
            else:
                last_status = 'inside'
        time.sleep(5)

# === 啟動監控背景任務 ===
def start_monitor():
    t = threading.Thread(target=monitor_job)
    t.daemon = True
    t.start()

start_monitor()

# === 執行 Web 服務 ===
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
