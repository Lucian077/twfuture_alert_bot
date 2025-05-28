import os
import requests
import time
import pandas as pd
from datetime import datetime, timedelta
import pytz
from flask import Flask

app = Flask(__name__)

# 設定台灣時區
tz = pytz.timezone('Asia/Taipei')

# Telegram 設定
TELEGRAM_TOKEN = '7863895518:AAH0avbUgC_yd7RoImzBvQJXFmIrKXjuSj8'
TELEGRAM_CHAT_ID = '1190387445'

# FinMind 設定
FINMIND_TOKEN = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNS0wNS0yOCAwMDo0OToxNiIsInVzZXJfaWQiOiJMdWNpYW4wNzciLCJpcCI6IjExMS4yNTQuMTI5LjIzMSJ9.o90BDk2IcDf0hvbfRrnJTOey4NoMj_WvhTU_Kdto-EU'

# 布林通道參數
PERIOD = 20
STD_DEV = 2
CHECK_INTERVAL = 10  # 每 10 秒檢查一次

# 資料暫存
historical_data = []
last_alert = {'direction': None}

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

        res = requests.get("https://api.finmindtrade.com/api/v4/data", params=payload, timeout=10)
        data = res.json()

        if data.get('status') != 200 or not data.get('data'):
            print(f"[{now.strftime('%H:%M:%S')}] 無法取得價格: API 無資料")
            return None

        df = pd.DataFrame(data['data'])
        df['datetime'] = pd.to_datetime(df['date'] + ' ' + df['time'])
        df = df.sort_values('datetime').reset_index(drop=True)

        latest_row = df.iloc[-1]
        return {
            'time': latest_row['datetime'].tz_localize('Asia/Taipei'),
            'price': latest_row['close'],
            'history': df[['datetime', 'close']].rename(columns={'datetime': 'time', 'close': 'price'}).to_dict(orient='records')
        }

    except Exception as e:
        print(f"[{datetime.now(tz).strftime('%H:%M:%S')}] 無法取得價格: {e}")
        return None

def calc_bollinger(prices):
    series = pd.Series(prices)
    ma = series.rolling(PERIOD).mean().iloc[-1]
    std = series.rolling(PERIOD).std().iloc[-1]
    upper = round(ma + STD_DEV * std, 2)
    lower = round(ma - STD_DEV * std, 2)
    return round(ma, 2), upper, lower

def send_telegram(msg):
    try:
        requests.post(
            f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage',
            json={'chat_id': TELEGRAM_CHAT_ID, 'text': msg, 'parse_mode': 'Markdown'},
            timeout=5
        )
        print(f"[{datetime.now(tz).strftime('%H:%M:%S')}] 發送通知成功")
    except Exception as e:
        print(f"[{datetime.now(tz).strftime('%H:%M:%S')}] 發送通知失敗: {e}")

def monitor():
    print(f"[{datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')}] 系統啟動中...")

    while True:
        data = get_price()
        if not data:
            time.sleep(CHECK_INTERVAL)
            continue

        historical_data.clear()
        historical_data.extend(data['history'])

        if len(historical_data) < PERIOD:
            print(f"[{datetime.now(tz).strftime('%H:%M:%S')}] 初始化資料不足")
            time.sleep(CHECK_INTERVAL)
            continue

        prices = [d['price'] for d in historical_data][-PERIOD:]
        ma, upper, lower = calc_bollinger(prices)
        price = data['price']
        ts = data['time'].strftime('%Y-%m-%d %H:%M:%S')

        print(f"\n[{ts}] 現價: {price} | 上軌: {upper} | 中軌: {ma} | 下軌: {lower}")

        if price > upper and last_alert['direction'] != 'upper':
            send_telegram(f"⚠️ *突破上軌！*\n時間：{ts}\n價格：`{price}`\n上軌：`{upper}`")
            last_alert['direction'] = 'upper'
        elif price < lower and last_alert['direction'] != 'lower':
            send_telegram(f"⚠️ *跌破下軌！*\n時間：{ts}\n價格：`{price}`\n下軌：`{lower}`")
            last_alert['direction'] = 'lower'
        elif lower <= price <= upper:
            last_alert['direction'] = None

        time.sleep(CHECK_INTERVAL)

@app.route('/')
def home():
    status = "初始化中" if not historical_data else "運行中"
    last_time = historical_data[-1]['time'].strftime('%Y-%m-%d %H:%M:%S') if historical_data else "無數據"
    last_price = historical_data[-1]['price'] if historical_data else "無"
    return f"""
    <h2>台指期布林通道監控系統</h2>
    狀態：{status}<br>
    最後更新時間：{last_time}<br>
    最後價格：{last_price}<br>
    """

if __name__ == '__main__':
    import threading
    threading.Thread(target=monitor, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 10000)))
