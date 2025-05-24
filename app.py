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
    now = datetime.now()
    data = []
    base_price = 18700
    for i in range(20):
        t = now.replace(second=0, microsecond=0) - pd.Timedelta(minutes=19 - i)
        close = base_price + np.random.randn() * 10
        open_ = close + np.random.randn()
        high = max(open_, close) + np.random.rand() * 5
        low = min(open_, close) - np.random.rand() * 5
        data.append([t, open_, high, low, close])
    df = pd.DataFrame(data, columns=["time", "open", "high", "low", "close"])
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
