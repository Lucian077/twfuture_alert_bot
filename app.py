import requests
import time
import pandas as pd
import numpy as np
from datetime import datetime

# 設定
BOLLINGER_PERIOD = 20  # 布林通道週期
BOLLINGER_STD = 2      # 標準差倍數
CHECK_INTERVAL = 5     # 檢查間隔(秒)
TELEGRAM_TOKEN = '7863895518:AAH0avbUgC_yd7RoImzBvQJXFmIrKXjuSj8'  # 請替換為自己的 Token
TELEGRAM_CHAT_ID = '1190387445'  # 請替換為自己的 Chat ID

# Yahoo Finance API 設定
YAHOO_SYMBOL = "WTX=F"  # 台指期近月代碼（Yahoo Finance 格式）
YAHOO_API_URL = f"https://query1.finance.yahoo.com/v8/finance/chart/{YAHOO_SYMBOL}?interval=1m"

# 初始化歷史數據
historical_data = []

def get_txf_price():
    """從 Yahoo Finance 獲取台指期近月即時價格"""
    try:
        response = requests.get(YAHOO_API_URL)
        data = response.json()
        
        # 解析最新價格
        latest_price = data["chart"]["result"][0]["meta"]["regularMarketPrice"]
        latest_time = data["chart"]["result"][0]["meta"]["regularMarketTime"]
        
        return {
            'timestamp': latest_time,
            'close': latest_price
        }
    except Exception as e:
        print(f"獲取價格失敗: {e}")
        return None

def calculate_bollinger_bands(data):
    """計算布林通道"""
    df = pd.DataFrame(data[-BOLLINGER_PERIOD:])
    df['MA'] = df['close'].rolling(window=BOLLINGER_PERIOD).mean()
    df['STD'] = df['close'].rolling(window=BOLLINGER_PERIOD).std()
    df['Upper'] = df['MA'] + (df['STD'] * BOLLINGER_STD)
    df['Lower'] = df['MA'] - (df['STD'] * BOLLINGER_STD)
    return df.iloc[-1]

def send_telegram_alert(message):
    """發送 Telegram 通知"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'Markdown'
        })
        print("Telegram 通知已發送")
    except Exception as e:
        print(f"發送通知失敗: {e}")

def monitor():
    print("=== 台指期布林通道監控系統啟動 ===")
    print("正在初始化歷史數據...")
    
    # 初始化 20 筆歷史數據
    while len(historical_data) < BOLLINGER_PERIOD:
        price_data = get_txf_price()
        if price_data:
            historical_data.append(price_data)
        time.sleep(1)
    
    print("歷史數據初始化完成，開始監控...")
    
    while True:
        latest_data = get_txf_price()
        if not latest_data:
            time.sleep(CHECK_INTERVAL)
            continue
        
        historical_data.append(latest_data)
        if len(historical_data) > BOLLINGER_PERIOD * 2:
            historical_data.pop(0)
        
        bb = calculate_bollinger_bands(historical_data)
        current_price = latest_data['close']
        
        print(f"\n時間: {datetime.fromtimestamp(latest_data['timestamp']).strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"當前價格: {current_price}")
        print(f"布林通道: {bb['Upper']:.2f} | {bb['MA']:.2f} | {bb['Lower']:.2f}")
        
        if current_price > bb['Upper']:
            alert_msg = f"*⚠️ 突破布林上軌!*\n價格: `{current_price}`\n上軌: `{bb['Upper']:.2f}`"
            send_telegram_alert(alert_msg)
        elif current_price < bb['Lower']:
            alert_msg = f"*⚠️ 突破布林下軌!*\n價格: `{current_price}`\n下軌: `{bb['Lower']:.2f}`"
            send_telegram_alert(alert_msg)
        
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    monitor()
