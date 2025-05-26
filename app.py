import os
import time
import requests
import pandas as pd
import numpy as np
import telegram
from flask import Flask
from datetime import datetime
from bs4 import BeautifulSoup

# Telegram 設定
TELEGRAM_TOKEN = '7863895518:AAH0avbUgC_yd7RoImzBvQJXFmIrKXjuSj8'
TELEGRAM_CHAT_ID = '1190387445'
bot = telegram.Bot(token=TELEGRAM_TOKEN)

# 建立 Flask App 用於 keep-alive
app = Flask(__name__)

@app.route('/')
def home():
    return 'Service is running'

# Yahoo 奇摩期貨網址
YAHOO_URL = "https://tw.stock.yahoo.com/future/futures-chart/WTXO1?period=1m"

# 建立歷史資料初始化用
def get_initial_kbars():
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    res = requests.get(YAHOO_URL, headers=headers)
    soup = BeautifulSoup(res.text, 'html.parser')
    scripts = soup.find_all('script')
    for script in scripts:
        if '__NUXT__=' in script.text:
            json_data = script.text.split('__NUXT__=')[1].strip()
            import json
            data = json.loads(json_data)
            try:
                k_data = data['data'][0]['priceChart']['chart']['technical']['WTXO1']['1m']
                df = pd.DataFrame(k_data)
                df['t'] = pd.to_datetime(df['t'], unit='s') + pd.Timedelta(hours=8)
                df = df.rename(columns={'t': 'time', 'c': 'close'})
                df = df[['time', 'close']]
                return df.tail(100)  # 初始化取 100 筆資料
            except Exception as e:
                print(f"❌ 初始化資料錯誤：{e}")
    return pd.DataFrame()

# 計算布林通道
def calculate_bollinger(df, period=20):
    df['MA'] = df['close'].rolling(window=period).mean()
    df['STD'] = df['close'].rolling(window=period).std()
    df['Upper'] = df['MA'] + 2 * df['STD']
    df['Lower'] = df['MA'] - 2 * df['STD']
    return df

# 發送 Telegram 訊息
def send_telegram_message(text):
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text)
    except Exception as e:
        print(f"❌ 傳送通知失敗：{e}")

# 主程式
def monitor():
    df = get_initial_kbars()
    if df.empty:
        print("❌ 無法初始化 K 線資料")
        return
    df = calculate_bollinger(df)

    last_alert_time = None
    while True:
        try:
            res = requests.get(YAHOO_URL, headers={"User-Agent": "Mozilla/5.0"})
            soup = BeautifulSoup(res.text, 'html.parser')
            scripts = soup.find_all('script')
            for script in scripts:
                if '__NUXT__=' in script.text:
                    json_data = script.text.split('__NUXT__=')[1].strip()
                    import json
                    data = json.loads(json_data)
                    k_data = data['data'][0]['priceChart']['chart']['technical']['WTXO1']['1m']
                    latest = pd.DataFrame(k_data).tail(1)
                    latest['t'] = pd.to_datetime(latest['t'], unit='s') + pd.Timedelta(hours=8)
                    latest = latest.rename(columns={'t': 'time', 'c': 'close'})
                    latest = latest[['time', 'close']]

                    df = pd.concat([df, latest]).drop_duplicates(subset='time', keep='last')
                    df = df.tail(100).reset_index(drop=True)
                    df = calculate_bollinger(df)

                    now = df.iloc[-1]
                    time_str = now['time'].strftime('%H:%M:%S')
                    close = now['close']
                    upper = now['Upper']
                    lower = now['Lower']

                    print(f"[{time_str}] 價格: {close} | 上軌: {upper} | 下軌: {lower}")

                    if close > upper:
                        send_telegram_message(f"🔺 [{time_str}] 價格突破上軌：{close:.2f} > {upper:.2f}")
                    elif close < lower:
                        send_telegram_message(f"🔻 [{time_str}] 價格跌破下軌：{close:.2f} < {lower:.2f}")
        except Exception as e:
            print(f"❌ 發生錯誤：{e}")
        time.sleep(5)

# 自動安裝缺少的套件
def install_requirements():
    try:
        import bs4
        import lxml
    except:
        os.system("pip install beautifulsoup4 lxml")

# 開始運作
if __name__ == '__main__':
    install_requirements()
    import threading
    threading.Thread(target=monitor).start()
    app.run(host='0.0.0.0', port=10000)
