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
    """從 Yahoo Finance 獲取台指期價格 (使用更可靠的API)"""
    try:
        # 使用更穩定的金融數據API
        url = "https://api.finmindtrade.com/api/v4/data?"
        params = {
            'dataset': 'TaiwanFuturesTick',
            'data_id': 'TX',
            'start_date': (datetime.now(taipei_tz) - timedelta(minutes=5)).strftime('%Y-%m-%d'),
            'end_date': datetime.now(taipei_tz).strftime('%Y-%m-%d')
        }
        headers = {'User-Agent': 'Mozilla/5.0'}
        
        response = requests.get(url, params=params, headers=headers)
        data = response.json()
        
        if data['status'] == 200 and len(data['data']) > 0:
            latest = data['data'][-1]
            return {
                'time': datetime.strptime(latest['date'] + ' ' + latest['Time'], '%Y-%m-%d %H:%M:%S').astimezone(taipei_tz),
                'price': latest['Close']
            }
        else:
            # 備用API
            url = "https://mis.taifex.com.tw/futures/api/getQuoteList/TX"
            data = requests.get(url).json()
            if data['rtCode'] == 0:
                latest = data['rtData'][0]
                return {
                    'time': datetime.now(taipei_tz),
                    'price': float(latest['c'])
                }
    except Exception as e:
        print(f"獲取價格失敗: {e}")
    return None

def calculate_bollinger():
    """計算布林通道"""
    if len(historical_data) < BOLLINGER_PERIOD:
        return {'upper': 0, 'lower': 0}
    
    prices = [x['price'] for x in historical_data[-BOLLINGER_PERIOD:]]
    ma = pd.Series(prices).mean()
    std = pd.Series(prices).std()
    return {
        'upper': ma + BOLLINGER_STD * std,
        'lower': ma - BOLLINGER_STD * std
    }

def send_alert(message):
    """發送 Telegram 通知"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'Markdown'
        })
        print(f"{datetime.now(taipei_tz).strftime('%H:%M:%S')} 已發送通知")
    except Exception as e:
        print(f"發送通知失敗: {e}")

def monitor():
    """主監控循環"""
    print(f"{datetime.now(taipei_tz).strftime('%Y-%m-%d %H:%M:%S')} 系統啟動中...")
    
    # 初始化歷史數據
    while len(historical_data) < BOLLINGER_PERIOD:
        price = get_price()
        if price and (not last_price or price['price'] != last_price):
            historical_data.append(price)
            last_price = price['price']
            print(f"初始化數據: {price['time'].strftime('%H:%M:%S')} - {price['price']}")
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
            
            if len(historical_data) > 50:  # 限制數據量
                historical_data.pop(0)
            
            bb = calculate_bollinger()
            
            print(f"\n時間: {price['time'].strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"價格: {price['price']}")
            print(f"布林通道: {bb['upper']:.2f} / {bb['lower']:.2f}")
            
            # 檢查突破
            if price['price'] > bb['upper']:
                if last_alert['direction'] != 'upper' or (time.time() - last_alert['time']) > 300:
                    send_alert(f"⚠️ 突破上軌!\n時間: {price['time'].strftime('%H:%M:%S')}\n價格: {price['price']}\n上軌: {bb['upper']:.2f}")
                    last_alert.update({'time': time.time(), 'direction': 'upper'})
            elif price['price'] < bb['lower']:
                if last_alert['direction'] != 'lower' or (time.time() - last_alert['time']) > 300:
                    send_alert(f"⚠️ 突破下軌!\n時間: {price['time'].strftime('%H:%M:%S')}\n價格: {price['price']}\n下軌: {bb['lower']:.2f}")
                    last_alert.update({'time': time.time(), 'direction': 'lower'})
        
        time.sleep(CHECK_INTERVAL)

@app.route('/')
def home():
    return f"台指期監控系統運行中<br>最後更新: {datetime.now(taipei_tz).strftime('%Y-%m-%d %H:%M:%S')}"

if __name__ == '__main__':
    import threading
    threading.Thread(target=monitor, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
