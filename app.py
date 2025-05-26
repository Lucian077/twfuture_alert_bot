import requests
import pandas as pd
import numpy as np
import time
import threading
from flask import Flask
import os

# === Telegram Bot 設定 ===
TELEGRAM_TOKEN = '你的 Telegram Bot Token'
CHAT_ID = '你的 Chat ID'

# === 建立 Flask App ===
app = Flask(__name__)

@app.route('/')
def home():
    return '台指期布林通道監控啟動中', 200

@app.route('/ping')
def ping():
    return 'pong', 200

# === 發送 Telegram 訊息 ===
def send_telegram_message(message):
    url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
    payload = {'chat_id': CHAT_ID, 'text': message}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f'發送錯誤：{e}')

# === 擷取 Yahoo 奇摩 台指期 即時資料 ===
def get_txf_price_from_yahoo():
    url = 'https://tw.stock.yahoo.com/future/quote/MTX%3DF'
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers)
        tables = pd.read_html(response.text)
        price_table = tables[0]
        current_price = float(price_table.iloc[0, 1])
        return current_price
    except Exception as e:
        print(f'❌ 發生錯誤：{e}')
        send_telegram_message(f'❌ 發生錯誤：{e}')
        return None

# === 記錄過去價格供布林通道使用 ===
price_history = []

# === 通知狀態，避免重複通知 ===
last_signal = None

# === 主監控邏輯 ===
def monitor():
    global last_signal
    while True:
        current_price = get_txf_price_from_yahoo()
        if current_price:
            price_history.append(current_price)
            if len(price_history) > 20:
                price_history.pop(0)

            if len(price_history) == 20:
                prices = np.array(price_history)
                mid = np.mean(prices)
                std = np.std(prices)
                upper = mid + 2 * std
                lower = mid - 2 * std

                now = time.strftime("%Y-%m-%d %H:%M:%S")

                if current_price > upper and last_signal != 'above':
                    msg = f"🚨 台指期突破布林上軌！\n時間：{now}\n價格：{current_price:.2f} > 上軌：{upper:.2f}"
                    send_telegram_message(msg)
                    last_signal = 'above'
                elif current_price < lower and last_signal != 'below':
                    msg = f"🚨 台指期跌破布林下軌！\n時間：{now}\n價格：{current_price:.2f} < 下軌：{lower:.2f}"
                    send_telegram_message(msg)
                    last_signal = 'below'
                elif lower <= current_price <= upper:
                    last_signal = 'inside'  # 不發送，只更新狀態
        time.sleep(5)

# === 背景執行監控 ===
threading.Thread(target=monitor, daemon=True).start()

# === 執行 Flask App ===
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
