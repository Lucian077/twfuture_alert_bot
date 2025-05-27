import os
import requests
import time
import pandas as pd
from datetime import datetime, timedelta
import pytz
from flask import Flask

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
CHECK_INTERVAL = 5

historical_data = []
last_alert = {'time': None, 'direction': None}
last_price = None

def get_price():
    try:
        end_time = datetime.now(taipei_tz)
        start_time = end_time - timedelta(minutes=3)
        
        url = "https://api.finmindtrade.com/api/v4/data"
        params = {
            'dataset': 'TaiwanFuturesTick',
            'data_id': 'TXF',
            'start_date': start_time.strftime('%Y-%m-%d'),
            'start_time': start_time.strftime('%H:%M:%S'),
            'end_time': end_time.strftime('%H:%M:%S'),
            'token': FINMIND_TOKEN
        }
        res = requests.get(url, params=params, timeout=5)
        data = res.json()
        
        if data.get("status") != 200 or not data.get("data"):
            print(f"[{datetime.now(taipei_tz).strftime('%H:%M:%S')}] 無資料")
            return None

        df = pd.DataFrame(data['data'])
        df['datetime'] = pd.to_datetime(df['date'] + ' ' + df['Time'])
        df = df.set_index('datetime').sort_index()

        # 轉為每分鐘的最後一筆價格（代表該分鐘的 close）
        df_resampled = df['Close'].resample('1min').last().dropna()
        latest_time = df_resampled.index[-1]
        latest_price = df_resampled.iloc[-1]

        return {
            'time': latest_time.tz_localize('Asia/Taipei'),
            'price': float(latest_price)
        }

    except Exception as e:
        print(f"[{datetime.now(taipei_tz).strftime('%H:%M:%S')}] 獲取價格失敗: {e}")
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
        print(f"[{datetime.now(taipei_tz).strftime('%H:%M:%S')}] 已發送通知")
    except Exception as e:
        print(f"[{datetime.now(taipei_tz).strftime('%H:%M:%S')}] 發送通知失敗: {e}")

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

    print("開始監控...")

    while True:
        price = get_price()
        if not price:
            time.sleep(CHECK_INTERVAL)
            continue

        if not last_price or price['price'] != last_price:
            historical_data.append(price)
            last_price = price['price']
            if len(historical_data) > 50:
                historical_data.pop(0)

            bb = calculate_bollinger()

            print(f"\n[{price['time'].strftime('%Y-%m-%d %H:%M:%S')}] 價格: {price['price']}")
            print(f"布林通道: 上軌={bb['upper']} 中軌={bb['ma']} 下軌={bb['lower']}")

            if price['price'] > bb['upper']:
                if not last_alert['time'] or (time.time() - last_alert['time']) > 300 or last_alert['direction'] != 'upper':
                    send_alert(f"⚠️ *突破上軌!*\n時間: {price['time'].strftime('%H:%M:%S')}\n價格: `{price['price']}`\n上軌: `{bb['upper']}`")
                    last_alert.update({'time': time.time(), 'direction': 'upper'})
            elif price['price'] < bb['lower']:
                if not last_alert['time'] or (time.time() - last_alert['time']) > 300 or last_alert['direction'] != 'lower':
                    send_alert(f"⚠️ *突破下軌!*\n時間: {price['time'].strftime('%H:%M:%S')}\n價格: `{price['price']}`\n下軌: `{bb['lower']}`")
                    last_alert.update({'time': time.time(), 'direction': 'lower'})

        time.sleep(CHECK_INTERVAL)

@app.route('/')
def home():
    status = "運行中" if historical_data else "初始化中"
    last_update = historical_data[-1]['time'].strftime('%Y-%m-%d %H:%M:%S') if historical_data else "無數據"
    return f"台指期監控系統 {status}<br>最後更新: {last_update}"

if __name__ == '__main__':
    import threading
    threading.Thread(target=monitor, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
