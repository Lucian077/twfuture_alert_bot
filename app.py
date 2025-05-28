import os
import time
import requests
import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup
from flask import Flask
import pytz
import threading

app = Flask(__name__)
taipei_tz = pytz.timezone('Asia/Taipei')

TELEGRAM_TOKEN = '7863895518:AAH0avbUgC_yd7RoImzBvQJXFmIrKXjuSj8'
TELEGRAM_CHAT_ID = '1190387445'

BOLLINGER_PERIOD = 20
BOLLINGER_STD = 2
CHECK_INTERVAL = 10  # 每 10 秒檢查一次

historical_data = []
last_price = None
last_alert = {'direction': None, 'time': None}

def fetch_yahoo_data():
    try:
        url = "https://tw.stock.yahoo.com/future/realtime/1"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(response.text, 'lxml')

        table = soup.find('table', class_='Fz(xs) Ta(end) Lh(20px)')
        rows = table.find_all('tr')
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 6:
                time_str = cols[0].text.strip()
                price_str = cols[1].text.strip().replace(',', '')
                try:
                    now = datetime.now(taipei_tz)
                    tick_time = datetime.strptime(f"{now.date()} {time_str}", "%Y-%m-%d %H:%M:%S").astimezone(taipei_tz)
                    return {'time': tick_time, 'price': float(price_str)}
                except:
                    continue
        print(f"[{datetime.now(taipei_tz).strftime('%H:%M:%S')}] 無法解析數據")
    except Exception as e:
        print(f"[{datetime.now(taipei_tz).strftime('%H:%M:%S')}] 無法取得價格: {e}")
    return None

def calculate_bollinger():
    if len(historical_data) < BOLLINGER_PERIOD:
        return {'upper': 0, 'lower': 0, 'ma': 0}
    prices = [x['price'] for x in historical_data[-BOLLINGER_PERIOD:]]
    series = pd.Series(prices)
    ma = series.mean()
    std = series.std()
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
        price_data = fetch_yahoo_data()
        if price_data:
            historical_data.append(price_data)
            last_price = price_data['price']
            print(f"[{price_data['time'].strftime('%H:%M:%S')}] 初始化價格: {price_data['price']}")
        time.sleep(2)

    print("✅ 開始監控...\n")
    while True:
        price_data = fetch_yahoo_data()
        if not price_data:
            time.sleep(CHECK_INTERVAL)
            continue

        if not last_price or price_data['price'] != last_price:
            last_price = price_data['price']
            historical_data.append(price_data)
            if len(historical_data) > 100:
                historical_data.pop(0)

            bb = calculate_bollinger()
            print(f"\n[{price_data['time'].strftime('%Y-%m-%d %H:%M:%S')}] 價格: {price_data['price']}")
            print(f"布林通道: 上軌 {bb['upper']} / 中軌 {bb['ma']} / 下軌 {bb['lower']}")

            if price_data['price'] > bb['upper']:
                if last_alert['direction'] != 'upper':
                    send_alert(f"⚠️ *突破上軌！*\n時間: {price_data['time'].strftime('%H:%M:%S')}\n價格: `{price_data['price']}`\n上軌: `{bb['upper']}`")
                    last_alert.update({'direction': 'upper', 'time': time.time()})
            elif price_data['price'] < bb['lower']:
                if last_alert['direction'] != 'lower':
                    send_alert(f"⚠️ *突破下軌！*\n時間: {price_data['time'].strftime('%H:%M:%S')}\n價格: `{price_data['price']}`\n下軌: `{bb['lower']}`")
                    last_alert.update({'direction': 'lower', 'time': time.time()})
            else:
                last_alert['direction'] = None

        time.sleep(CHECK_INTERVAL)

@app.route('/')
def home():
    status = "運行中" if historical_data else "初始化中"
    last_update = historical_data[-1]['time'].strftime('%Y-%m-%d %H:%M:%S') if historical_data else "無數據"
    return f"台指期布林通道監控系統<br>狀態：{status}<br>最後更新：{last_update}"

if __name__ == '__main__':
    threading.Thread(target=monitor, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
