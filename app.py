import pandas as pd
import numpy as np
import requests
import time
import os
from datetime import datetime
from flask import Flask
from threading import Thread

# Telegram 設定（Render 中使用環境變數）
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }
    requests.post(url, data=data)

# 模擬抓取台指期 24 小時盤的資料
def get_simulated_txf_data():
    now = datetime.now()
    base = 18000  # 模擬基準價
    data = []
    for i in range(100):
        ts = now.timestamp() - (99 - i) * 60  # 每分鐘
        price = base + np.random.randn() * 10
        data.append([datetime.fromtimestamp(ts), price])
    df = pd.DataFrame(data, columns=["time", "close"])
    return df

# 計算布林通道
def compute_bollinger_bands(df, period=20, stddev=2):
    df['ma'] = df['close'].rolling(period).mean()
    df['std'] = df['close'].rolling(period).std()
    df['upper'] = df['ma'] + stddev * df['std']
    df['lower'] = df['ma'] - stddev * df['std']
    return df

# 主邏輯：每 5 秒監控一次
def main():
    df = get_simulated_txf_data()
    df = compute_bollinger_bands(df)
    latest = df.iloc[-1]
    price = latest['close']
    upper = latest['upper']
    lower = latest['lower']

    message = f"📊 台指期 1 分鐘布林通道監控\n時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    if price >= upper:
        message += "\n📈 價格觸碰布林【上軌】"
    elif price <= lower:
        message += "\n📉 價格觸碰布林【下軌】"
    else:
        message += "\n✅ 價格在布林通道內"
    
    send_telegram_message(message)

# Flask 網頁服務設定
app = Flask(__name__)

@app.route('/')
def index():
    return "✅ 台指期布林通道監控機器人正在運作中！"

@app.route('/ping')
def ping():
    return "✅ PONG - Bot 活著！"

# 同時運行 Flask 和主監控邏輯
if __name__ == "__main__":
    def run_flask():
        app.run(host="0.0.0.0", port=10000)

    def monitor_loop():
        while True:
            try:
                main()
            except Exception as e:
                print(f"⚠️ 錯誤：{e}")
            time.sleep(5)

    Thread(target=run_flask).start()
    Thread(target=monitor_loop).start()
