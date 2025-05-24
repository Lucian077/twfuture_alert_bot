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
    requests.post(url, data=data)

def get_realtime_txf_data():
    url = "https://www.taifex.com.tw/cht/3/futDailyMarketReport"
    try:
        now = datetime.now().strftime('%Y/%m/%d')
        df = pd.read_html(url)[0]
        df.columns = df.columns.droplevel()
        df = df[df["商品"] == "台指期貨"]
        price = float(df["成交價格"].iloc[0])
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return pd.DataFrame([[timestamp, price]], columns=["time", "close"])
    except Exception as e:
        print("無法取得即時資料:", e)
        return pd.DataFrame(columns=["time", "close"])

def compute_bollinger_bands(df, period=20, stddev=2):
    df["ma"] = df["close"].rolling(period).mean()
    df["std"] = df["close"].rolling(period).std()
    df["upper"] = df["ma"] + stddev * df["std"]
    df["lower"] = df["ma"] - stddev * df["std"]
    return df

def monitor():
    history = []
    last_alert = None
    while True:
        new_data = get_realtime_txf_data()
        if not new_data.empty:
            history.append(new_data.iloc[0])
            if len(history) > 100:
                history.pop(0)
            df = pd.DataFrame(history)
            df = compute_bollinger_bands(df)
            latest = df.iloc[-1]
            price = latest["close"]
            upper = latest["upper"]
            lower = latest["lower"]

            alert_message = None
            if price >= upper:
                alert_message = f"🚨 台指期突破布林上緣\n價格：{price}\n時間：{latest['time']}"
            elif price <= lower:
                alert_message = f"🚨 台指期跌破布林下緣\n價格：{price}\n時間：{latest['time']}"

            if alert_message and alert_message != last_alert:
                send_telegram_message(alert_message)
                last_alert = alert_message

        time.sleep(5)

@app.route("/ping")
def ping():
    return "pong", 200

if __name__ == "__main__":
    import threading
    threading.Thread(target=monitor).start()
    app.run(host="0.0.0.0", port=10000)
