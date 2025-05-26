import requests
import pandas as pd
import time
from flask import Flask
import threading
from datetime import datetime
import numpy as np
import telegram
import os

# Telegram 設定
BOT_TOKEN = '你的 Telegram Bot Token'
CHAT_ID = '你的 Chat ID'
bot = telegram.Bot(token=BOT_TOKEN)

# Flask ping 保活
app = Flask(__name__)

@app.route('/ping')
def ping():
    return "pong", 200

def fetch_realtime_txf():
    url = "https://tw.stock.yahoo.com/future/futures-intraday/TXF%26WTXO1?sid=TXF&bf=1"
    try:
        response = requests.get(url, timeout=10)
        tables = pd.read_html(response.text, flavor='html5lib')
        df = tables[1]
        df.columns = ['時間', '買進', '賣出', '成交', '漲跌', '幅度', '單量', '總量', '未平倉', '內盤', '外盤']
        df = df[df['成交'] != '-']
        df['成交'] = df['成交'].str.replace(',', '').astype(float)
        df['時間'] = pd.to_datetime(df['時間'])
        df = df.sort_values(by='時間')
        return df[['時間', '成交']]
    except Exception as e:
        print("❌ 抓取即時資料失敗：", e)
        return None

def check_bollinger_and_notify():
    last_status = None

    while True:
        df = fetch_realtime_txf()
        if df is None or len(df) < 20:
            time.sleep(5)
            continue

        close_prices = df['成交']
        ma = close_prices.rolling(window=20).mean()
        std = close_prices.rolling(window=20).std()
        upper = ma + 2 * std
        lower = ma - 2 * std

        current_price = close_prices.iloc[-1]
        upper_band = upper.iloc[-1]
        lower_band = lower.iloc[-1]
        current_time = df['時間'].iloc[-1].strftime("%Y-%m-%d %H:%M:%S")

        if current_price > upper_band:
            if last_status != 'upper':
                bot.send_message(chat_id=CHAT_ID, text=f"📈 台指期突破布林上軌！\n時間：{current_time}\n價格：{current_price:.2f}")
                last_status = 'upper'
        elif current_price < lower_band:
            if last_status != 'lower':
                bot.send_message(chat_id=CHAT_ID, text=f"📉 台指期跌破布林下軌！\n時間：{current_time}\n價格：{current_price:.2f}")
                last_status = 'lower'
        else:
            last_status = 'inside'

        time.sleep(5)

# 背景執行
threading.Thread(target=check_bollinger_and_notify, daemon=True).start()

# 正確啟動方式（讓 Render 可識別）
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
