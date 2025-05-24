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

def get_simulated_txf_data():
    def get_simulated_txf_data():
    now = datetime.now().strftime("%H:%M:%S")
    data = []

    # 模擬一段布林資料
    for i in range(19):
        data.append([now, 20000 + i])  # 正常價格

    # 最後一筆資料 = 觸碰上軌的價格
    data.append([now, 20030])  # 模擬價格突破布林上緣

    df = pd.DataFrame(data, columns=["time", "close"])
    return df

def compute_bollinger_bands(df, period=20, stddev=2):
    df['ma'] = df['close'].rolling(period).mean()
    df['std'] = df['close'].rolling(period).std()
    df['upper'] = df['ma'] + stddev * df['std']
    df['lower'] = df['ma'] - stddev * df['std']
    return df

def main():
    df = get_simulated_txf_data()
    df = compute_bollinger_bands(df)
    latest = df.iloc[-1]
    price = latest['close']
    upper = latest['upper']
    lower = latest['lower']

    message = f"📊 台指期 1 分鐘布林通道監控\n時間: {latest['time']}\n價格: {price:.2f}\n上軌: {upper:.2f}\n下軌: {lower:.2f}"

    if price >= upper:
        message += "\n📈 價格觸碰布林【上軌】"
    elif price <= lower:
        message += "\n📉 價格觸碰布林【下軌】"
    else:
        message += "\n✅ 價格在布林通道內"

    send_telegram_message(message)

if __name__ == "__main__":
    main()
