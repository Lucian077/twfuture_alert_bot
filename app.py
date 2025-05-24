import pandas as pd
import numpy as np
import requests
from datetime import datetime
import time
import os
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
    try:
        requests.post(url, data=data)
    except Exception as e:
        print("Telegram 發送錯誤：", e)

def get_simulated_txf_data():
    now = datetime.now().strftime("%H:%M:%S")
    price = float(requests.get("https://openapi.sinotrade.com.tw/v1/real/1101").json().get("z", 18000))  # 模擬價格
    data = [[now, price]]
    df = pd.DataFrame(data, columns=["time", "close"])
    return df

def compute_bollinger_bands(df, period=20, stddev=2):
    df['ma'] = df['close'].rolling(period).mean()
    df['std'] = df['close'].rolling(period).std()
    df['upper'] = df['ma'] + stddev * df['std']
    df['lower'] = df['ma'] - stddev * df['std']
    return df

@app.route('/ping')
def ping():
    return "✅ Bot is alive!"

def monitor_loop():
    history = []

    while True:
        df = get_simulated_txf_data()
        history.append(df.iloc[0])
        df = pd.DataFrame(history)

        if len(df) < 20:
            time.sleep(5)
            continue

        df = compute_bollinger_bands(df)
        latest = df.iloc[-1]
        price = latest['close']
        upper = latest['upper']
        lower = latest['lower']

        if pd.isna(upper) or pd.isna(lower):
            time.sleep(5)
            continue

        if price >= upper:
            message = f"📈 台指期價格突破布林上軌！\n價格：{price}\n時間：{latest['time']}"
            send_telegram_message(message)
        elif price <= lower:
            message = f"📉 台指期價格跌破布林下軌！\n價格：{price}\n時間：{latest['time']}"
            send_telegram_message(message)

        time.sleep(5)

if __name__ == "__main__":
    import threading
    threading.Thread(target=monitor_loop).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
