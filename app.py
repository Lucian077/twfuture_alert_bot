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
    url = "https://tw.stock.yahoo.com/future/real/MTX%26"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    tables = pd.read_html(response.text)
    df = tables[0]
    df.columns = df.columns.droplevel(0)  # 移除多層欄位
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    price = float(df.iloc[0]["成交"])
    return pd.DataFrame([[now, price]], columns=["time", "close"])

def compute_bollinger_bands(df, period=20, stddev=2):
    df['ma'] = df['close'].rolling(period).mean()
    df['std'] = df['close'].rolling(period).std()
    df['upper'] = df['ma'] + stddev * df['std']
    df['lower'] = df['ma'] - stddev * df['std']
    return df

@app.route("/ping")
def ping():
    return "pong"

def main():
    df_all = []

    while True:
        try:
            df_new = get_realtime_txf_data()
            df_all.append(df_new.iloc[0])
            df = pd.DataFrame(df_all)
            df = compute_bollinger_bands(df)

            latest = df.iloc[-1]
            price = latest['close']
            upper = latest['upper']
            lower = latest['lower']

            message = f"📊 台指期即時監控\n時間：{latest['time']}\n價格：{price:.2f}"

            if pd.isna(upper) or pd.isna(lower):
                message += "\n⚠️ 資料尚未足夠計算布林通道"
            elif price >= upper:
                message += "\n🚀 價格突破布林【上軌】"
            elif price <= lower:
                message += "\n📉 價格跌破布林【下軌】"
            else:
                message += "\n✅ 價格在布林通道內"

            send_telegram_message(message)

        except Exception as e:
            send_telegram_message(f"❌ 發生錯誤：{e}")

        time.sleep(5)

if __name__ == "__main__":
    from threading import Thread
    Thread(target=main).start()
    app.run(host="0.0.0.0", port=10000)
