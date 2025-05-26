import requests
import pandas as pd
import numpy as np
import time
import telegram
from flask import Flask

# Telegram 設定
TELEGRAM_TOKEN = '7863895518:AAH0avbUgC_yd7RoImzBvQJXFmIrKXjuSj8'
TELEGRAM_CHAT_ID = '1190387445'
bot = telegram.Bot(token=TELEGRAM_TOKEN)

# Yahoo 台指期近月一網址
URL = 'https://tw.stock.yahoo.com/future/charts.html?sid=WTX%26&sname=臺指期近一&mid=01&type=1'

# 建立 Flask App 做 keep-alive
app = Flask(__name__)

@app.route('/')
def home():
    return 'OK'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36'
}

last_status = None

def fetch_price_table():
    try:
        response = requests.get(URL, headers=HEADERS)
        tables = pd.read_html(response.text)
        for table in tables:
            if '時間' in table.columns and '成交' in table.columns:
                return table
        return None
    except Exception as e:
        print(f"❌ 發生錯誤：{e}")
        return None

def monitor_bollinger():
    global last_status
    history = []

    while True:
        table = fetch_price_table()
        if table is None:
            time.sleep(5)
            continue

        table = table[['時間', '成交']].dropna()
        table = table[::-1].reset_index(drop=True)
        table['成交'] = pd.to_numeric(table['成交'], errors='coerce')
        table = table.dropna()

        history.extend(table['成交'].tolist())
        history = history[-20:]

        if len(history) < 20:
            time.sleep(5)
            continue

        series = pd.Series(history)
        ma = series.mean()
        std = series.std()
        upper = ma + 2 * std
        lower = ma - 2 * std
        current_price = history[-1]

        status = 'in'
        if current_price > upper:
            status = 'above'
        elif current_price < lower:
            status = 'below'

        if status != 'in' and status != last_status:
            msg = f"⚠️ 台指期價格突破布林通道！\\n目前價格：{current_price}\\n上緣：{round(upper,2)} 下緣：{round(lower,2)}"
            try:
                bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)
                print("✅ 已通知 Telegram")
            except Exception as e:
                print(f"❌ 傳送 Telegram 通知失敗：{e}")
        last_status = status

        time.sleep(5)

if __name__ == '__main__':
    import threading
    threading.Thread(target=monitor_bollinger).start()
    app.run(host='0.0.0.0', port=10000)
