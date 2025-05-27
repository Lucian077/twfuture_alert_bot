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

# 設定 Telegram 通知 (請替換成你的資訊)
TELEGRAM_TOKEN = '7863895518:AAH0avbUgC_yd7RoImzBvQJXFmIrKXjuSj8'
TELEGRAM_CHAT_ID = '1190387445'

# 布林通道設定
BOLLINGER_PERIOD = 20
BOLLINGER_STD = 2
CHECK_INTERVAL = 5  # 檢查間隔(秒)

# 初始化變數
historical_data = []
last_alert = {'time': None, 'direction': None}
last_price = None

def get_price():
    """獲取台指期價格 (使用更穩定的數據源)"""
    try:
        # 方法1: 使用公開的期貨API
        url = "https://api.finmindtrade.com/api/v4/data?"
        params = {
            'dataset': 'TaiwanFuturesTick',
            'data_id': 'TX',
            'start_date': (datetime.now(taipei_tz) - timedelta(minutes=30)).strftime('%Y-%m-%d'),
            'token': 'free'  # 免費token
        }
        response = requests.get(url, params=params, timeout=5)
        data = response.json()
        
        if data.get('status') == 200 and len(data.get('data', [])) > 0:
            latest = data['data'][-1]
            return {
                'time': datetime.strptime(f"{latest['date']} {latest['Time']}", '%Y-%m-%d %H:%M:%S').astimezone(taipei_tz),
                'price': float(latest['Close'])
            }
        
        # 方法2: 備用API (Yahoo Finance)
        url = "https://query1.finance.yahoo.com/v8/finance/chart/%5ETWII?interval=1m&region=US"
        headers = {'User-Agent': 'Mozilla/5.0'}
        data = requests.get(url, headers=headers, timeout=5).json()
        if 'chart' in data and 'result' in data['chart']:
            meta = data['chart']['result'][0]['meta']
            return {
                'time': datetime.fromtimestamp(meta['regularMarketTime'], taipei_tz),
                'price': meta['regularMarketPrice']
            }
            
    except Exception as e:
        print(f"[{datetime.now(taipei_tz).strftime('%H:%M:%S')}] 獲取價格失敗: {str(e)}")
    
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
        response = requests.post(url, json={
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'Markdown'
        }, timeout=5)
        print(f"[{datetime.now(taipei_tz).strftime('%H:%M:%S')}] 已發送通知")
        return True
    except Exception as e:
        print(f"[{datetime.now(taipei_tz).strftime('%H:%M:%S')}] 發送通知失敗: {str(e)}")
        return False

def monitor():
    """主監控循環"""
    print(f"[{datetime.now(taipei_tz).strftime('%Y-%m-%d %H:%M:%S')}] 系統啟動中...")
    
    # 初始化歷史數據
    while len(historical_data) < BOLLINGER_PERIOD:
        price = get_price()
        if price and (not last_price or price['price'] != last_price):
            historical_data.append(price)
            last_price = price['price']
            print(f"[{price['time'].strftime('%H:%M:%S')}] 初始化數據: {price['price']}")
        time.sleep(1)
    
    print("開始監控...")
    
    while True:
        price = get_price()
        if not price:
            time.sleep(CHECK_INTERVAL)
            continue
            
        # 只更新價格變動時的數據
        if not last_price or price['price'] != last_price:
            historical_data.append(price)
            last_price = price['price']
            
            if len(historical_data) > 50:
                historical_data.pop(0)
            
            bb = calculate_bollinger()
            
            print(f"\n[{price['time'].strftime('%Y-%m-%d %H:%M:%S')}] 價格: {price['price']}")
            print(f"布林通道: {bb['upper']} / {bb['ma']} / {bb['lower']}")
            
            # 檢查突破
            if price['price'] > bb['upper']:
                if not last_alert['time'] or (time.time() - last_alert['time']) > 300 or last_alert['direction'] != 'upper':
                    if send_alert(f"⚠️ *突破上軌!*\n時間: {price['time'].strftime('%H:%M:%S')}\n價格: `{price['price']}`\n上軌: `{bb['upper']}`"):
                        last_alert.update({'time': time.time(), 'direction': 'upper'})
            elif price['price'] < bb['lower']:
                if not last_alert['time'] or (time.time() - last_alert['time']) > 300 or last_alert['direction'] != 'lower':
                    if send_alert(f"⚠️ *突破下軌!*\n時間: {price['time'].strftime('%H:%M:%S')}\n價格: `{price['price']}`\n下軌: `{bb['lower']}`"):
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
