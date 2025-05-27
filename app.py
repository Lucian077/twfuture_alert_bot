import os
import requests
import time
import pandas as pd
from datetime import datetime
import pytz
from flask import Flask

app = Flask(__name__)

# 設定台灣時區
taipei_tz = pytz.timezone('Asia/Taipei')

# Telegram 通知設定（已內建）
TELEGRAM_TOKEN = '7863895518:AAH0avbUgC_yd7RoImzBvQJXFmIrKXjuSj8'
TELEGRAM_CHAT_ID = '1190387445'

# 布林通道參數
BOLLINGER_PERIOD = 20
BOLLINGER_STD = 2
CHECK_INTERVAL = 5  # 每 5 秒檢查一次

# 全域變數
historical_data = []
last_alert = {'time': None, 'direction': None}
last_price = None

def get_price():
    """從 Yahoo 奇摩台指期近月一獲取最新價格與時間"""
    try:
        url = "https://tw.stock.yahoo.com/future/futures-indices/TXFR1?period=1m"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=5)
        tables = pd.read_html(response.text)
        df = tables[1]  # 第 2 個表格是 1 分 K 線

        df.columns = ['時間', '開盤', '最高', '最低', '收盤', '成交量']
        df = df.dropna()
        latest = df.iloc[-1]

        now = datetime.now(taipei_tz).replace(second=0, microsecond=0)
        price = float(latest['收盤'])
        return {'time': now, 'price': price}
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
        print(f"[{datetime.now(taipei_tz).strftime('%H:%M:%S')}] ✅ 已發送通知")
    except Exception as e:
        print(f"[{datetime.now(taipei_tz).strftime('%H:%M:%S')}] ❌ 發送通知失敗: {e}")

def monitor():
    """主監控迴圈"""
    global last_price
    print(f"[{datetime.now(taipei_tz).strftime('%Y-%m-%d %H:%M:%S')}] 系統啟動中...")

    while len(historical_data) < BOLLINGER_PERIOD:
        price = get_price()
        if price and (not last_price or price['price'] != last_price):
            historical_data.append(price)
            last_price = price['price']
            print(f"[{price['time'].strftime('%H:%M:%S')}] 初始化: {price['price']}")
        time.sleep(1)

    print("✅ 初始化完成，開始監控...")

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
            print(f"布林通道：上軌={bb['upper']} / 中線={bb['ma']} / 下軌={bb['lower']}")

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
    if historical_data:
        last_data = historical_data[-1]
        bb = calculate_bollinger()
        return f"""
        台指期監控系統：{status}<br>
        最後更新時間：{last_data['time'].strftime('%Y-%m-%d %H:%M:%S')}<br>
        最新價格：{last_data['price']}<br>
        布林通道：<br>
        &emsp;上軌：{bb['upper']}<br>
        &emsp;中線：{bb['ma']}<br>
        &emsp;下軌：{bb['lower']}<br>
        """
    else:
        return f"台指期監控系統：{status}<br>尚未取得資料"

if __name__ == '__main__':
    import threading
    threading.Thread(target=monitor, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
