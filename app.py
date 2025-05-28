import os
import time
import requests
import pandas as pd
from datetime import datetime, timedelta
import pytz
from flask import Flask
from bs4 import BeautifulSoup

app = Flask(__name__)

# Telegram 設定
TELEGRAM_TOKEN = '7863895518:AAH0avbUgC_yd7RoImzBvQJXFmIrKXjuSj8'
TELEGRAM_CHAT_ID = '1190387445'

# 時區與布林通道設定
tz = pytz.timezone('Asia/Taipei')
BOLL_PERIOD = 20
BOLL_STD = 2
INTERVAL = 5

# 資料儲存
historical_data = []
last_alert = {'time': None, 'direction': None}
last_price = None

def get_price_from_yahoo():
    try:
        url = "https://tw.stock.yahoo.com/futures/real/MTXF?contractCode=MTX%26MTXW1"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')

        table = soup.find('table', class_='Fz(1rem) Bdcl(c)')
        if not table:
            raise ValueError("No matching table found")

        rows = table.find_all('tr')[1:]  # skip header
        prices = []

        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 6:
                time_str = cols[0].text.strip()
                price_str = cols[1].text.strip().replace(',', '')

                if time_str and price_str:
                    dt_str = datetime.now(tz).strftime('%Y-%m-%d') + ' ' + time_str
                    dt = datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S').astimezone(tz)
                    price = float(price_str)
                    prices.append({'time': dt, 'price': price})

        if prices:
            return prices[-1]  # 最新一筆
        else:
            raise ValueError("No prices extracted")

    except Exception as e:
        print(f"[{datetime.now(tz).strftime('%H:%M:%S')}] 無法取得價格: {e}")
        return None

def calculate_bollinger():
    if len(historical_data) < BOLL_PERIOD:
        return {'upper': 0, 'lower': 0, 'ma': 0}
    prices = [x['price'] for x in historical_data[-BOLL_PERIOD:]]
    ma = pd.Series(prices).mean()
    std = pd.Series(prices).std()
    return {
        'upper': round(ma + BOLL_STD * std, 2),
        'lower': round(ma - BOLL_STD * std, 2),
        'ma': round(ma, 2)
    }

def send_alert(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'Markdown'
        }, timeout=5)
        print(f"[{datetime.now(tz).strftime('%H:%M:%S')}] ✅ 已發送通知")
        return True
    except Exception as e:
        print(f"[{datetime.now(tz).strftime('%H:%M:%S')}] ❌ 發送通知失敗: {e}")
        return False

def monitor():
    global last_price
    print(f"[{datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')}] 系統啟動中...")

    # 初始化歷史資料
    while len(historical_data) < BOLL_PERIOD:
        data = get_price_from_yahoo()
        if data and (not last_price or data['price'] != last_price):
            historical_data.append(data)
            last_price = data['price']
            print(f"[{data['time'].strftime('%H:%M:%S')}] 初始化價格: {data['price']}")
        time.sleep(1)

    print("✅ 初始化完成，開始監控...")

    while True:
        data = get_price_from_yahoo()
        if not data:
            time.sleep(INTERVAL)
            continue

        if not last_price or data['price'] != last_price:
            historical_data.append(data)
            last_price = data['price']
            if len(historical_data) > 50:
                historical_data.pop(0)

            bb = calculate_bollinger()
            print(f"\n[{data['time'].strftime('%H:%M:%S')}] 價格: {data['price']}")
            print(f"布林通道: 上軌={bb['upper']} 中軌={bb['ma']} 下軌={bb['lower']}")

            if data['price'] > bb['upper']:
                if not last_alert['time'] or (time.time() - last_alert['time']) > 300 or last_alert['direction'] != 'upper':
                    if send_alert(f"⚠️ *突破上軌!*\n時間: {data['time'].strftime('%H:%M:%S')}\n價格: `{data['price']}`\n上軌: `{bb['upper']}`"):
                        last_alert.update({'time': time.time(), 'direction': 'upper'})

            elif data['price'] < bb['lower']:
                if not last_alert['time'] or (time.time() - last_alert['time']) > 300 or last_alert['direction'] != 'lower':
                    if send_alert(f"⚠️ *跌破下軌!*\n時間: {data['time'].strftime('%H:%M:%S')}\n價格: `{data['price']}`\n下軌: `{bb['lower']}`"):
                        last_alert.update({'time': time.time(), 'direction': 'lower'})

        time.sleep(INTERVAL)

@app.route('/')
def home():
    status = "✅ 運行中" if historical_data else "⏳ 初始化中"
    last_update = historical_data[-1]['time'].strftime('%Y-%m-%d %H:%M:%S') if historical_data else "尚無資料"
    return f"<h3>台指期監控系統狀態</h3><p>{status}</p><p>最後更新: {last_update}</p>"

if __name__ == '__main__':
    import threading
    threading.Thread(target=monitor, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
