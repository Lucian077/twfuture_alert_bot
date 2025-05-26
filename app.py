from flask import Flask
import threading
import requests
import pandas as pd
import time
import telegram
from bs4 import BeautifulSoup

# === Telegram 設定 ===
TELEGRAM_TOKEN = '7863895518:AAH0avbUgC_yd7RoImzBvQJXFmIrKXjuSj8'
TELEGRAM_CHAT_ID = '1190387445'
bot = telegram.Bot(token=TELEGRAM_TOKEN)

# === 初始化 Flask ===
app = Flask(__name__)

# === 發送通知用 ===
last_signal = None  # 防止重複通知

# === 取得 Yahoo 台指期 1分K ===
def fetch_taifex_data():
    url = 'https://tw.stock.yahoo.com/future/futures-chart?sid=WTX%26'
    res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
    soup = BeautifulSoup(res.text, 'html.parser')
    script_tags = soup.find_all("script")
    for tag in script_tags:
        if "ChartApi" in tag.text:
            json_start = tag.text.find("[{\"timestamp\"")
            json_end = tag.text.find("}]") + 2
            raw_json = tag.text[json_start:json_end]
            try:
                df = pd.read_json(raw_json)
                df["datetime"] = pd.to_datetime(df["timestamp"], unit="s")
                df = df.rename(columns={
                    "open": "開盤", "high": "最高", "low": "最低", "close": "收盤"
                })
                return df[["datetime", "開盤", "最高", "最低", "收盤"]].tail(60).reset_index(drop=True)
            except Exception as e:
                print(f"❌ JSON 解析錯誤：{e}")
    return pd.DataFrame()

# === 檢查突破布林通道邏輯 ===
def check_bollinger_breakout():
    global last_signal
    df = fetch_taifex_data()
    if df.empty or len(df) < 20:
        print("資料不足，無法計算布林通道")
        return

    df['MA20'] = df['收盤'].rolling(window=20).mean()
    df['STD20'] = df['收盤'].rolling(window=20).std()
    df['Upper'] = df['MA20'] + 2 * df['STD20']
    df['Lower'] = df['MA20'] - 2 * df['STD20']

    latest = df.iloc[-1]
    price = latest['收盤']
    upper = latest['Upper']
    lower = latest['Lower']

    if price > upper and last_signal != 'break_up':
        msg = f"📈 台指期突破上軌！\n價格：{price:.2f} > 上軌：{upper:.2f}"
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)
        last_signal = 'break_up'

    elif price < lower and last_signal != 'break_down':
        msg = f"📉 台指期跌破下軌！\n價格：{price:.2f} < 下軌：{lower:.2f}"
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)
        last_signal = 'break_down'

# === 背景執行任務 ===
def run_monitor():
    while True:
        try:
            check_bollinger_breakout()
        except Exception as e:
            print(f"❌ 發生錯誤：{e}")
        time.sleep(5)

# === Keep Alive 用 ===
@app.route('/')
def home():
    return "OK", 200

# === 啟動背景執行緒 + Web 服務 ===
if __name__ == '__main__':
    threading.Thread(target=run_monitor, daemon=True).start()
    app.run(host='0.0.0.0', port=10000)
