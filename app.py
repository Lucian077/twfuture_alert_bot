import os
import requests
import time
import pandas as pd
from datetime import datetime, timedelta
import pytz
from flask import Flask
from threading import Thread

app = Flask(__name__)

# 時區設定
taipei_tz = pytz.timezone('Asia/Taipei')

# Telegram 設定
TELEGRAM_TOKEN = '7863895518:AAH0avbUgC_yd7RoImzBvQJXFmIrKXjuSj8'
TELEGRAM_CHAT_ID = '1190387445'

# 布林通道參數
BOLLINGER_PERIOD = 20
BOLLINGER_STD = 2
CHECK_INTERVAL = 5

# 狀態記憶
historical_data = []
last_alert = {'time': None, 'direction': None}
last_price = None

def get_price():
    """從 Yahoo 奇摩擷取台指期近月一的最新價格"""
    try:
        url = "https://tw.stock.yahoo.com/future/realtime/TXF%261"
        headers = {'User-Agent': 'Mozilla/5.0'}
        tables = pd.read_html(requests.get(url, headers=headers, timeout=10).text)

        # 第 1 個表格中包含最新價格
        for table in tables:
            if '成交' in table.columns:
                row = table.iloc[0]
                price = float(row['成交'])
                t = datetime.now(taipei_tz)
                return {'price': price, 'time': t}
    except Exception as e:
        print(f"[{datetime.now(taipei_tz).strftime('%H:%M:%S')}] 無法取得價格: {e}")
    return None

def calculate_bollinger():
    """計算布林通道"""
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
    """發送 Telegram 通知"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'Markdown'
        }, timeout=5)
        print(f"[{datetime.now(taipei_tz).strftime('%H:%M:%S')}] 已發送通知")
    except Exception as e:
        print(f"[{datetime.now(taipei_tz).strftime('%H:%M:%S')}] 通知失敗: {e}")

def monitor():
    global last_price

    print(f"[{datetime.now(taipei_tz).strftime('%Y-%m-%d %H:%M:%S')}] 系統啟動中...")

    # 初始化歷史資料
    while len(historical_data) < BOLLINGER_PERIOD:
        price = get_price()
        if price:
            historical_data.append(price)
            last_price = price['price']
            print(f"[{price['time'].strftime('%H:%M:%S')}] 初始化: {price['price']}")
        time.sleep(1)

    print("✅ 開始監控...\n")

    # 持續監控
    while True:
        price = get_price()
        if not price:
            time.sleep(CHECK_INTERVAL)
            continue

        if price['price'] != last_price:
            historical_data.append(price)
            last_price = price['price']
            if len(historical_data) > 100:
                historical_data.pop(0)

            bb = calculate_bollinger()

            print(f"\n[{price['time'].strftime('%Y-%m-%d %H:%M:%S')}] 價格: {price['price']}")
            print(f"布林通道 ➤ 上: {bb['upper']} 中: {bb['ma']} 下: {bb['lower']}")

            if price['price'] > bb['upper']:
                if not last_alert['time'] or time.time() - last_alert['time'] > 300 or last_alert['direction'] != 'upper':
                    send_alert(f"⚠️ *突破上軌!*\n時間: {price['time'].strftime('%H:%M:%S')}\n價格: `{price['price']}`\n上軌: `{bb['upper']}`")
                    last_alert.update({'time': time.time(), 'direction': 'upper'})
            elif price['price'] < bb['lower']:
                if not last_alert['time'] or time.time() - last_alert['time'] > 300 or last_alert['direction'] != 'lower':
                    send_alert(f"⚠️ *突破下軌!*\n時間: {price['time'].strftime('%H:%M:%S')}\n價格: `{price['price']}`\n下軌: `{bb['lower']}`")
                    last_alert.update({'time': time.time(), 'direction': 'lower'})

        time.sleep(CHECK_INTERVAL)

@app.route('/')
def home():
    status = "✅ 運行中" if historical_data else "⏳ 初始化中"
    last = historical_data[-1]['time'].strftime('%Y-%m-%d %H:%M:%S') if historical_data else "無"
    return f"台指期布林通道監控：{status}<br>最後更新：{last}"

if __name__ == '__main__':
    Thread(target=monitor, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
