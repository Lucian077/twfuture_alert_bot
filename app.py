import pandas as pd
import numpy as np
import requests
from datetime import datetime
import time
import os

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }
    requests.post(url, data=data)

def get_txf_1min_data():
    url = "https://www.taifex.com.tw/cht/3/futDataDown"
    payload = {
        "down_type": "1",           # 分線
        "commodity_id": "TXF",      # 小台期貨
    }
    try:
        res = requests.post(url, data=payload)
        df = pd.read_html(res.text)[0]

        # 清理資料格式
        df.columns = ["時間", "成交價", "漲跌", "買價", "賣價", "成交量"]
        df = df[["時間", "成交價"]]
        df["time"] = pd.to_datetime(df["時間"]).dt.strftime("%H:%M:%S")
        df["close"] = pd.to_numeric(df["成交價"], errors="coerce")
        df = df.dropna()
        df = df[["time", "close"]].reset_index(drop=True)
        return df.tail(30)
    except Exception as e:
        print("資料抓取失敗:", e)
        return pd.DataFrame(columns=["time", "close"])

def compute_bollinger_bands(df, period=20, stddev=2):
    df['ma'] = df['close'].rolling(period).mean()
    df['std'] = df['close'].rolling(period).std()
    df['upper'] = df['ma'] + stddev * df['std']
    df['lower'] = df['ma'] - stddev * df['std']
    return df

def monitor_loop():
    while True:
        df = get_txf_1min_data()
        if df.empty or len(df) < 20:
            print("資料不足，略過本次檢查")
            time.sleep(5)
            continue

        df = compute_bollinger_bands(df)
        latest = df.iloc[-1]
        price = latest['close']
        upper = latest['upper']
        lower = latest['lower']

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = f"📊 台指期 1 分鐘布林通道監控\n時間：{now}\n當前價格：{price:.2f}"

        if price >= upper:
            message += "\n📈 價格觸碰布林【上軌】"
        elif price <= lower:
            message += "\n📉 價格觸碰布林【下軌】"
        else:
            message += "\n✅ 價格在布林通道內"

        send_telegram_message(message)
        time.sleep(5)

if __name__ == "__main__":
    monitor_loop()
