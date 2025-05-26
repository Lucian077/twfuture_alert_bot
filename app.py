import requests
import pandas as pd
import numpy as np
import time
import telegram
from flask import Flask

# === Telegram 設定 ===
TELEGRAM_TOKEN = '7863895518:AAH0avbUgC_yd7RoImzBvQJXFmIrKXjuSj8'
TELEGRAM_CHAT_ID = '1190387445'
bot = telegram.Bot(token=TELEGRAM_TOKEN)

# === Flask 設定（保持 Render 存活）===
app = Flask(__name__)
@app.route("/")
def keep_alive():
    return "Bot is running!"

# === Yahoo 台指期近月一的 URL ===
YAHOO_URL = "https://tw.stock.yahoo.com/future/charts.html?sid=WTX&contractId=WTX%26"

# === 自訂 headers 模擬瀏覽器 ===
HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# === 儲存上次通知狀態，避免重複通知 ===
last_signal = None

# === 下載歷史資料並建立初始布林通道基準 ===
def get_kline_data():
    try:
        response = requests.get(YAHOO_URL, headers=HEADERS, timeout=10)
        tables = pd.read_html(response.text, flavor='html5lib')
        df = tables[1]  # 通常表格 1 是 1 分 K 線資料
        df.columns = ['時間', '成交價', '漲跌', '單量', '總量', '未平倉']
        df = df[['時間', '成交價']].dropna()
        df['成交價'] = pd.to_numeric(df['成交價'], errors='coerce')
        df = df.dropna()
        df.reset_index(drop=True, inplace=True)
        return df
    except Exception as e:
        print(f"❌ 發生錯誤：{e}")
        return None

# === 計算布林通道（20MA ± 2SD）===
def calculate_bollinger(df):
    df['MA20'] = df['成交價'].rolling(window=20).mean()
    df['STD20'] = df['成交價'].rolling(window=20).std()
    df['Upper'] = df['MA20'] + 2 * df['STD20']
    df['Lower'] = df['MA20'] - 2 * df['STD20']
    return df

# === 發送 Telegram 訊息 ===
def send_telegram_message(message):
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        print(f"✅ 已發送通知：{message}")
    except Exception as e:
        print(f"❌ 傳送 Telegram 訊息錯誤：{e}")

# === 主邏輯迴圈 ===
def monitor():
    global last_signal
    while True:
        df = get_kline_data()
        if df is not None and len(df) >= 20:
            df = calculate_bollinger(df)
            latest = df.iloc[-1]
            price = latest['成交價']
            upper = latest['Upper']
            lower = latest['Lower']
            timestamp = latest['時間']

            if price > upper:
                if last_signal != 'upper':
                    send_telegram_message(f"⚠️ [{timestamp}] 台指期觸碰布林通道上緣：{price:.2f}")
                    last_signal = 'upper'
            elif price < lower:
                if last_signal != 'lower':
                    send_telegram_message(f"⚠️ [{timestamp}] 台指期觸碰布林通道下緣：{price:.2f}")
                    last_signal = 'lower'
            else:
                last_signal = None

        time.sleep(5)

# === 在啟動時執行監控程式 ===
import threading
threading.Thread(target=monitor).start()

# === 啟動 Flask App（保持 Render 存活）===
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
