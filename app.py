import os
import requests
import time
import pandas as pd
from datetime import datetime
from flask import Flask

app = Flask(__name__)

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

def get_price():
    """從 Yahoo Finance 獲取台指期價格"""
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/%5ETWII?interval=1m"
        headers = {'User-Agent': 'Mozilla/5.0'}
        data = requests.get(url, headers=headers).json()
        return {
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'price': data['chart']['result'][0]['meta']['regularMarketPrice']
        }
    except:
        print("獲取價格失敗")
        return None

def calculate_bollinger():
    """計算布林通道"""
    df = pd.DataFrame(historical_data[-BOLLINGER_PERIOD:])
    df['MA'] = df['price'].rolling(BOLLINGER_PERIOD).mean()
    df['STD'] = df['price'].rolling(BOLLINGER_PERIOD).std()
    return {
        'upper': df['MA'].iloc[-1] + BOLLINGER_STD * df['STD'].iloc[-1],
        'lower': df['MA'].iloc[-1] - BOLLINGER_STD * df['STD'].iloc[-1]
    }

def send_alert(message):
    """發送 Telegram 通知"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message
        })
        print("已發送通知:", message)
    except:
        print("發送通知失敗")

def monitor():
    """主監控循環"""
    print("系統啟動中...")
    
    # 初始化歷史數據
    while len(historical_data) < BOLLINGER_PERIOD:
        price = get_price()
        if price:
            historical_data.append(price)
        time.sleep(1)
    
    print("開始監控...")
    
    while True:
        price = get_price()
        if not price:
            time.sleep(CHECK_INTERVAL)
            continue
            
        historical_data.append(price)
        if len(historical_data) > 50:  # 限制數據量
            historical_data.pop(0)
        
        bb = calculate_bollinger()
        current_price = price['price']
        
        print(f"\n時間: {price['time']}")
        print(f"價格: {current_price}")
        print(f"布林通道: {bb['upper']:.2f} / {bb['lower']:.2f}")
        
        # 檢查突破
        if current_price > bb['upper']:
            if last_alert['direction'] != 'upper' or (time.time() - last_alert['time']) > 300:
                send_alert(f"⚠️ 突破上軌!\n價格: {current_price}\n上軌: {bb['upper']:.2f}")
                last_alert.update({'time': time.time(), 'direction': 'upper'})
        elif current_price < bb['lower']:
            if last_alert['direction'] != 'lower' or (time.time() - last_alert['time']) > 300:
                send_alert(f"⚠️ 突破下軌!\n價格: {current_price}\n下軌: {bb['lower']:.2f}")
                last_alert.update({'time': time.time(), 'direction': 'lower'})
        
        time.sleep(CHECK_INTERVAL)

@app.route('/')
def home():
    return "台指期監控系統運行中"

if __name__ == '__main__':
    import threading
    threading.Thread(target=monitor, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
