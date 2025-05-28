# app.py
import time
import requests
import pandas as pd
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import pytz
import numpy as np

# === Telegram 設定 ===
TELEGRAM_TOKEN = '7863895518:AAH0avbUgC_yd7RoImzBvQJXFmIrKXjuSj8'
CHAT_ID = '1190387445'

# === 時區 ===
tz = pytz.timezone('Asia/Taipei')

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': CHAT_ID, 'text': message}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"發送 Telegram 訊息失敗: {e}")

def fetch_yahoo_txf_nearby1():
    url = "https://tw.stock.yahoo.com/future/quote/TXF%26MTF1"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    try:
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, "html.parser")
        table = soup.find("table")
        rows = table.find_all("tr")[1:]
        data = []
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 2:
                continue
            time_str = cols[0].text.strip()
            price_str = cols[1].text.strip().replace(",", "")
            try:
                price = float(price_str)
                now = datetime.now(tz)
                dt = datetime.strptime(time_str, "%H:%M").replace(year=now.year, month=now.month, day=now.day)
                dt = tz.localize(dt)
                data.append((dt, price))
            except:
                continue
        df = pd.DataFrame(data, columns=["datetime", "price"]).set_index("datetime")
        return df
    except Exception as e:
        print(f"❌ 抓取失敗: {e}")
        return None

def calculate_bollinger(df, window=20):
    df['ma'] = df['price'].rolling(window).mean()
    df['std'] = df['price'].rolling(window).std()
    df['upper'] = df['ma'] + 2 * df['std']
    df['lower'] = df['ma'] - 2 * df['std']
    return df

# === 主迴圈 ===
history_df = None

while True:
    df = fetch_yahoo_txf_nearby1()
    if df is None or df.empty:
        print(f"[{datetime.now(tz).strftime('%H:%M:%S')}] 無法取得資料，稍後重試")
        time.sleep(10)
        continue

    # 累積歷史資料
    if history_df is None:
        history_df = df
    else:
        history_df = pd.concat([history_df, df])
        history_df = history_df[~history_df.index.duplicated(keep='last')]
        history_df = history_df.sort_index().last("60min")

    history_df = calculate_bollinger(history_df)
    latest = history_df.iloc[-1]

    # 顯示狀態
    print(f"[{latest.name.strftime('%H:%M:%S')}] 價格: {latest.price}, 上軌: {latest.upper:.2f}, 下軌: {latest.lower:.2f}")

    # 判斷突破
    if latest.price > latest.upper:
        send_telegram_message(f"⚠️ 價格突破上軌！\n目前價格：{latest.price}\n時間：{latest.name.strftime('%H:%M:%S')}")
    elif latest.price < latest.lower:
        send_telegram_message(f"⚠️ 價格跌破下軌！\n目前價格：{latest.price}\n時間：{latest.name.strftime('%H:%M:%S')}")

    time.sleep(10)
