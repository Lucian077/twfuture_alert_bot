import requests
import pandas as pd
import time
import numpy as np
import telegram
from flask import Flask

app = Flask(__name__)

# Telegram 設定（已自動帶入）
TELEGRAM_TOKEN = '7863895518:AAH0avbUgC_yd7RoImzBvQJXFmIrKXjuSj8'
TELEGRAM_CHAT_ID = '1190387445'
bot = telegram.Bot(token=TELEGRAM_TOKEN)

# 記錄是否已通知過，避免重複通知
notified_upper = False
notified_lower = False

# 抓取 Yahoo 台指期近月一資料
def fetch_yahoo_future_data():
    url = "https://tw.stock.yahoo.com/future/futures-chart?sid=WTX1&interval=1m"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    try:
        res = requests.get(url, headers=headers, timeout=10)
        tables = pd.read_html(res.text, flavor='html5lib')
        for table in tables:
            if '時間' in table.columns and '成交' in table.columns:
                df = table[['時間', '成交']].copy()
                df = df[df['成交'].apply(lambda x: isinstance(x, (int, float)) or str(x).replace('.', '', 1).isdigit())]
                df['成交'] = pd.to_numeric(df['成交'])
                df['時間'] = pd.to_datetime(df['時間'], format='%H:%M')
                df = df.sort_values('時間')
                return df
        raise ValueError("找不到正確的表格")
    except Exception as e:
        print("❌ 發生錯誤：", e)
        return None

# 計算布林通道上下緣
def calculate_bollinger_bands(prices, period=20, num_std=2):
    rolling_mean = prices.rolling(window=period).mean()
    rolling_std = prices.rolling(window=period).std()
    upper_band = rolling_mean + num_std * rolling_std
    lower_band = rolling_mean - num_std * rolling_std
    return rolling_mean, upper_band, lower_band

# 初始化過去資料
historical_data = None
while historical_data is None or len(historical_data) < 20:
    historical_data = fetch_yahoo_future_data()
    if historical_data is None:
        print("等待 Yahoo 資料...")
        time.sleep(5)

print("✅ 初始化完成，共取得 {} 筆資料".format(len(historical_data)))

# 每 5 秒監控價格
def monitor():
    global notified_upper, notified_lower, historical_data
    while True:
        new_data = fetch_yahoo_future_data()
        if new_data is not None and not new_data.empty:
            # 合併新舊資料，取最後 20 筆
            combined = pd.concat([historical_data, new_data]).drop_duplicates('時間')
            combined = combined.sort_values('時間').iloc[-20:]
            historical_data = combined

            prices = combined['成交']
            ma, upper, lower = calculate_bollinger_bands(prices)

            current_price = prices.iloc[-1]
            current_time = combined['時間'].iloc[-1].strftime("%H:%M")

            if current_price > upper.iloc[-1]:
                if not notified_upper:
                    message = f"⚠️ [{current_time}] 台指期價格突破布林通道上緣\n價格：{current_price}\n上緣：{upper.iloc[-1]:.2f}"
                    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
                    notified_upper = True
                    notified_lower = False
            elif current_price < lower.iloc[-1]:
                if not notified_lower:
                    message = f"⚠️ [{current_time}] 台指期價格跌破布林通道下緣\n價格：{current_price}\n下緣：{lower.iloc[-1]:.2f}"
                    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
                    notified_lower = True
                    notified_upper = False
            else:
                notified_upper = False
                notified_lower = False

        time.sleep(5)

# 開始背景執行
import threading
threading.Thread(target=monitor, daemon=True).start()

# Flask keep-alive 用
@app.route('/')
def index():
    return 'OK', 200

# Render 專用啟動設定
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
