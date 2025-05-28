from datetime import datetime, timedelta
import pytz
import requests
import pandas as pd
import numpy as np
import time
import threading
from flask import Flask

# --- 設定區 ---
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNS0wNS0yOCAwMDo0OToxNiIsInVzZXJfaWQiOiJMdWNpYW4wNzciLCJpcCI6IjExMS4yNTQuMTI5LjIzMSJ9.o90BDk2IcDf0hvbfRrnJTOey4NoMj_WvhTU_Kdto-EU"
TELEGRAM_TOKEN = "7863895518:AAH0avbUgC_yd7RoImzBvQJXFmIrKXjuSj8"
CHAT_ID = "1190387445"
CHECK_INTERVAL = 10  # 每 10 秒檢查一次
tz = pytz.timezone("Asia/Taipei")

latest_price = None
latest_update = "初始化中"
status_lock = threading.Lock()

# --- 函式區 ---
def get_price():
    try:
        now = datetime.now(tz)
        start_time = (now - timedelta(minutes=60)).strftime('%Y-%m-%d %H:%M:%S')
        end_time = now.strftime('%Y-%m-%d %H:%M:%S')

        payload = {
            'dataset': 'TaiwanFuturesMinuteKBar',
            'data_id': 'TXF',
            'start_time': start_time,
            'end_time': end_time,
            'token': FINMIND_TOKEN
        }

        response = requests.get('https://api.finmindtrade.com/api/v4/data', params=payload)
        data = response.json()

        if not data.get('data'):
            print(f"[{now.strftime('%H:%M:%S')}] 無法取得價格：API 無資料")
            return None

        df = pd.DataFrame(data['data'])
        df['datetime'] = pd.to_datetime(df['datetime']).dt.tz_localize("UTC").dt.tz_convert(tz)
        df.set_index('datetime', inplace=True)
        df = df[['close']].copy()
        df.columns = ['price']
        return df

    except Exception as e:
        print(f"[{datetime.now(tz).strftime('%H:%M:%S')}] 無法取得價格: {e}")
        return None

def calc_bollinger(df, window=20, num_std=2):
    df['MA'] = df['price'].rolling(window=window).mean()
    df['STD'] = df['price'].rolling(window=window).std()
    df['Upper'] = df['MA'] + (num_std * df['STD'])
    df['Lower'] = df['MA'] - (num_std * df['STD'])
    return df

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': CHAT_ID, 'text': message}
    requests.post(url, data=payload)

def monitor():
    global latest_price, latest_update

    while True:
        df = get_price()
        if df is None or len(df) < 20:
            with status_lock:
                latest_update = "無數據"
            time.sleep(CHECK_INTERVAL)
            continue

        df = calc_bollinger(df)
        latest = df.iloc[-1]
        price = latest['price']
        upper = latest['Upper']
        lower = latest['Lower']
        ts = df.index[-1].strftime('%Y-%m-%d %H:%M:%S')

        message = None
        if price > upper:
            message = f"⚠️ 價格突破上緣！\n時間：{ts}\n價格：{price:.2f}\n上緣：{upper:.2f}"
        elif price < lower:
            message = f"⚠️ 價格跌破下緣！\n時間：{ts}\n價格：{price:.2f}\n下緣：{lower:.2f}"

        if message:
            send_telegram_message(message)
            print(f"[{ts}] 已發送通知：{message.replace(chr(10), ' | ')}")
        else:
            print(f"[{ts}] 價格正常：{price:.2f}，上緣：{upper:.2f}，下緣：{lower:.2f}")

        with status_lock:
            latest_price = price
            latest_update = ts

        time.sleep(CHECK_INTERVAL)

# --- Web 狀態顯示 ---
app = Flask(__name__)

@app.route("/")
def index():
    with status_lock:
        price = f"{latest_price:.2f}" if latest_price else "無"
        return f"""
        <h2>台指期布林通道監控系統</h2>
        <p>狀態：監控中</p>
        <p>最後更新時間：{latest_update}</p>
        <p>最後價格：{price}</p>
        """

# --- 主程式 ---
if __name__ == "__main__":
    t = threading.Thread(target=monitor)
    t.daemon = True
    t.start()
    app.run(host="0.0.0.0", port=10000)
