import requests
import pandas as pd
import numpy as np
import time
import telegram
from flask import Flask
from bs4 import BeautifulSoup

# Telegram 設定
TELEGRAM_TOKEN = '7863895518:AAH0avbUgC_yd7RoImzBvQJXFmIrKXjuSj8'
TELEGRAM_CHAT_ID = '1190387445'
bot = telegram.Bot(token=TELEGRAM_TOKEN)

# 初始化 Flask
app = Flask(__name__)

@app.route('/')
def keep_alive():
    return 'OK'

def fetch_tw_futures_data():
    url = 'https://tw.stock.yahoo.com/future/1m/WTX%26'
    headers = {
        'User-Agent': 'Mozilla/5.0'
    }

    try:
        res = requests.get(url, headers=headers)
        dfs = pd.read_html(res.text)
        df = dfs[0]

        df.columns = ['時間', '成交價', '買進', '賣出', '成交量', '單量', '未平倉', '']
        df = df.drop(columns=['', '買進', '賣出', '單量', '未平倉'])

        df = df[df['成交價'] != '-']
        df['成交價'] = df['成交價'].astype(float)
        df = df[::-1].reset_index(drop=True)  # 時間順序排列
        return df

    except Exception as e:
        print(f"❌ 發生錯誤：{e}")
        return None

def calc_bollinger_band(prices, window=20, num_std=2):
    rolling_mean = prices.rolling(window=window).mean()
    rolling_std = prices.rolling(window=window).std()
    upper_band = rolling_mean + (rolling_std * num_std)
    lower_band = rolling_mean - (rolling_std * num_std)
    return rolling_mean, upper_band, lower_band

def monitor():
    notified = False

    while True:
        df = fetch_tw_futures_data()
        if df is None or len(df) < 20:
            print("⏳ 等待更多資料...")
            time.sleep(5)
            continue

        prices = df['成交價']
        ma, upper, lower = calc_bollinger_band(prices)

        latest_price = prices.iloc[-1]
        latest_upper = upper.iloc[-1]
        latest_lower = lower.iloc[-1]

        print(f"🔍 時間：{df['時間'].iloc[-1]}｜價格：{latest_price}｜上緣：{latest_upper:.2f}｜下緣：{latest_lower:.2f}")

        if latest_price > latest_upper:
            if not notified:
                msg = f"🔔 價格突破上緣！\n價格：{latest_price} > 上緣：{latest_upper:.2f}"
                bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)
                print("✅ 已發送上緣通知")
                notified = True

        elif latest_price < latest_lower:
            if not notified:
                msg = f"🔔 價格跌破下緣！\n價格：{latest_price} < 下緣：{latest_lower:.2f}"
                bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)
                print("✅ 已發送下緣通知")
                notified = True

        else:
            notified = False  # 若未再突破，重設通知狀態

        time.sleep(5)

if __name__ == '__main__':
    import threading
    threading.Thread(target=monitor).start()
    app.run(host='0.0.0.0', port=10000)
