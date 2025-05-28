import os
import requests
import time
import pandas as pd
from datetime import datetime, timedelta
import pytz
from flask import Flask
import threading

app = Flask(__name__)

# 設定台灣時區
taipei_tz = pytz.timezone('Asia/Taipei')

# Telegram 設定
TELEGRAM_TOKEN = '7863895518:AAH0avbUgC_yd7RoImzBvQJXFmIrKXjuSj8'
TELEGRAM_CHAT_ID = '1190387445'

# FinMind API Token
FINMIND_TOKEN = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNS0wNS0yOCAwMDo0OToxNiIsInVzZXJfaWQiOiJMdWNpYW4wNzciLCJpcCI6IjExMS4yNTQuMTI5LjIzMSJ9.o90BDk2IcDf0hvbfRrnJTOey4NoMj_WvhTU_Kdto-EU'

# 布林通道設定
BOLLINGER_PERIOD = 20
BOLLINGER_STD = 2
CHECK_INTERVAL = 10  # 每 10 秒檢查一次

# 初始化
historical_data = []
last_price = None

def get_price():
    """取得台指期近月一價格 (1分K)"""
    try:
        url = "https://api.finmindtrade.com/api/v4/data"
        params = {
            'dataset': 'TaiwanFutures1Min',
            'data_id': 'TXF1',
            'start_date': (datetime.now(taipei_tz) - timedelta(minutes=30)).strftime('%Y-%m-%d'),
            'token': FINMIND_TOKEN
        }
        response = requests.get(url, params=params, timeout=5)
        data = response.json()
        records = data.get("data", [])

        if not records:
            print(f"[{datetime.now(taipei_tz).strftime('%H:%M:%S')}] 無法取得價格: API 無資料")
            return None

        latest = records[-1]
        time_obj = datetime.strptime(f"{latest['date']} {latest['datetime'][-8:]}", "%Y-%m-%d %H:%M:%S").astimezone(taipei_tz)
        return {
            'time': time_obj,
            'price': float(latest['close'])
        }

    except Exception as e:
        print(f"[{datetime.now(taipei_tz).strftime('%H:%M:%S')}] 無法取得價格: {str(e)}")
        return None

def calculate_bollinger():
    if len(historical_data) < BOLLINGER_PERIOD:
        return {'upper': 0, 'lower': 0, 'ma': 0}

    prices = [x['price'] for x in historical_data[-BOLLINGER_PERIOD:]]
    ma = pd.Series(prices).mean()
    std = pd.Series(prices).std()
    return {
        'upper': round(ma + BOLLINGER_STD * std, 2),
        'lower': round(ma - BOLLINGER_STD * std, 2),
        'ma': round(ma, 2)
    }

def send_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'Markdown'
        }, timeout=5)
        print(f"[{datetime.now(taipei_tz).strftime('%H:%M:%S')}] ✅ 已發送通知")
    except Exception as e:
        print(f"[{datetime.now(taipei_tz).strftime('%H:%M:%S')}] ❌ 發送通知失敗: {str(e)}")

def monitor():
    global last_price
    print(f"[{datetime.now(taipei_tz).strftime('%Y-%m-%d %H:%M:%S')}] 系統啟動中...")

    while len(historical_data) < BOLLINGER_PERIOD:
        price = get_price()
        if price and (not last_price or price['price'] != last_price):
            historical_data.append(price)
            last_price = price['price']
            print(f"[{price['time'].strftime('%H:%M:%S')}] 初始化數據: {price['price']}")
        time.sleep(2)

    print("✅ 開始監控...\n")

    while True:
        price = get_price()
        if not price:
            time.sleep(CHECK_INTERVAL)
            continue

        if not last_price or price['price'] != last_price:
            historical_data.append(price)
            last_price = price['price']
            if len(historical_data) > 100:
                historical_data.pop(0)

            bb = calculate_bollinger()

            print(f"\n[{price['time'].strftime('%Y-%m-%d %H:%M:%S')}] 價格: {price['price']}")
            print(f"布林通道 ➤ 上軌: {bb['upper']} / 中軌: {bb['ma']} / 下軌: {bb['lower']}")

            # 突破即時通知
            if price['price'] > bb['upper']:
                send_alert(f"⚠️ *突破上軌!*\n時間: {price['time'].strftime('%H:%M:%S')}\n價格: `{price['price']}`\n上軌: `{bb['upper']}`")
            elif price['price'] < bb['lower']:
                send_alert(f"⚠️ *突破下軌!*\n時間: {price['time'].strftime('%H:%M:%S')}\n價格: `{price['price']}`\n下軌: `{bb['lower']}`")

        time.sleep(CHECK_INTERVAL)

@app.route('/')
def home():
    status = "運行中" if historical_data else "初始化中"
    last_update = historical_data[-1]['time'].strftime('%Y-%m-%d %H:%M:%S') if historical_data else "無數據"
    return f"台指期監控系統狀態: {status}<br>最後更新: {last_update}"

if __name__ == '__main__':
    threading.Thread(target=monitor, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
