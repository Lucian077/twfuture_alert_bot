import os
import time
import requests
import pandas as pd
from datetime import datetime
from flask import Flask
import pytz
import threading

app = Flask(__name__)

# 台灣時區
taipei_tz = pytz.timezone('Asia/Taipei')

# Telegram 設定
TELEGRAM_TOKEN = '7863895518:AAH0avbUgC_yd7RoImzBvQJXFmIrKXjuSj8'
TELEGRAM_CHAT_ID = '1190387445'

# 布林通道參數
BOLLINGER_PERIOD = 20
BOLLINGER_STD = 2
CHECK_INTERVAL = 5  # 每 5 秒檢查

# 全域變數
historical_data = []
last_alert = {'time': None, 'direction': None}
last_price = None

def get_price():
    """從 Yahoo 奇摩抓取「台指期近月一」價格"""
    try:
        url = "https://tw.stock.yahoo.com/future/realtime/TXF%261"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        dfs = pd.read_html(response.text)

        for df in dfs:
            if '成交' in df.iloc[:, 0].astype(str).values or '成交價' in df.iloc[:, 0].astype(str).values:
                for i in range(len(df)):
                    if '成交' in str(df.iloc[i, 0]) or '成交價' in str(df.iloc[i, 0]):
                        price = float(str(df.iloc[i, 1]).replace(',', '').strip())
                        t = datetime.now(taipei_tz)
                        return {'price': price, 'time': t}

        raise ValueError("找不到含成交價的表格")

    except Exception as e:
        print(f"[{datetime.now(taipei_tz).strftime('%H:%M:%S')}] 無法取得價格: {e}")
    return None

def calculate_bollinger():
    """計算布林通道上下軌"""
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
        print(f"[{datetime.now(taipei_tz).strftime('%H:%M:%S')}] ✅ 已發送通知")
    except Exception as e:
        print(f"[{datetime.now(taipei_tz).strftime('%H:%M:%S')}] ❌ 發送通知失敗: {e}")

def monitor():
    """主監控邏輯"""
    global last_price

    print(f"[{datetime.now(taipei_tz).strftime('%Y-%m-%d %H:%M:%S')}] 系統啟動中...")

    # 初始化歷史資料
    while len(historical_data) < BOLLINGER_PERIOD:
        price = get_price()
        if price and (not last_price or price['price'] != last_price):
            historical_data.append(price)
            last_price = price['price']
            print(f"[{price['time'].strftime('%H:%M:%S')}] 初始化: {price['price']}")
        time.sleep(1)

    print("✅ 開始監控...")

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
            print(f"布林通道 ➤ 上: {bb['upper']} | 中: {bb['ma']} | 下: {bb['lower']}")

            # 判斷突破
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
    status = "✅ 運行中" if historical_data else "🔄 初始化中"
    last_update = historical_data[-1]['time'].strftime('%Y-%m-%d %H:%M:%S') if historical_data else "無資料"
    return f"台指期布林通道監控系統<br>狀態：{status}<br>最後更新：{last_update}"

if __name__ == '__main__':
    threading.Thread(target=monitor, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
