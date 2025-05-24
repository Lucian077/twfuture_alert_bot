import os
import time
import threading
import requests
import pandas as pd
import numpy as np
from datetime import datetime
from flask import Flask

app = Flask(__name__)

# Telegram 設定
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    requests.post(url, data=data)

# 即時取得台指期報價（來自期交所 API）
def fetch_txf_price():
    try:
        url = "https://www.taifex.com.tw/cht/3/futDataDown"
        payload = {
            "down_type": "1",
            "commodity_id": "TX",
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        response = requests.post(url, data=payload, headers=headers)
        df = pd.read_html(response.text)[0]

        # 篩出近月台指期的最新一筆價格
        df = df[df["契約"] == "TX"]
        price = float(df["結算價"].values[0])
        return price
    except Exception as e:
        print("資料取得失敗", e)
        return None

# 計算布林通道
def compute_bollinger_bands(prices, period=20, stddev=2):
    df = pd.DataFrame(prices, columns=["close"])
    df["ma"] = df["close"].rolling(period).mean()
    df["std"] = df["close"].rolling(period).std()
    df["upper"] = df["ma"] + stddev * df["std"]
    df["lower"] = df["ma"] - stddev * df["std"]
    return df

# 主邏輯
def monitor_txf():
    prices = []

    while True:
        price = fetch_txf_price()
        if price:
            prices.append(price)
            if len(prices) > 100:
                prices.pop(0)

            if len(prices) >= 20:
                df = compute_bollinger_bands(prices)
                latest = df.iloc[-1]
                upper = latest["upper"]
                lower = latest["lower"]

                message = f"📈 台指期監控\n時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n現價：{price}"

                if price >= upper:
                    message += "\n🚀 價格突破布林【上軌】"
                    send_telegram_message(message)
                elif price <= lower:
                    message += "\n📉 價格跌破布林【下軌】"
                    send_telegram_message(message)

        time.sleep(5)

# Flask route for ping
@app.route("/ping")
def ping():
    return "pong", 200

@app.route("/")
def home():
    return "TW Future Alert Bot Running.", 200

# 背景執行
def start_monitor():
    t = threading.Thread(target=monitor_txf)
    t.daemon = True
    t.start()

# 執行 Web 與監控
if __name__ == "__main__":
    start_monitor()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
