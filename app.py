from flask import Flask
import time
import threading
import requests
import pandas as pd
import numpy as np
import telegram
from bs4 import BeautifulSoup

app = Flask(__name__)

# Telegram 設定
TELEGRAM_TOKEN = '7863895518:AAH0avbUgC_yd7RoImzBvQJXFmIrKXjuSj8'
TELEGRAM_CHAT_ID = '1190387445'
bot = telegram.Bot(token=TELEGRAM_TOKEN)

# 儲存歷史資料
history_df = pd.DataFrame(columns=['Time', 'Price'])

# 爬取 Yahoo 奇摩台指期近月一 1 分 K 線資料
def fetch_price():
    url = "https://tw.stock.yahoo.com/future/1min/WFX0"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, "lxml")

        table = soup.find("table")
        if not table:
            raise Exception("找不到表格")

        rows = table.find_all("tr")[1:]  # 跳過表頭

        data = []
        for row in rows:
            cols = row.find_all("td")
            if len(cols) >= 2:
                time_text = cols[0].text.strip()
                price_text = cols[1].text.strip().replace(",", "")
                try:
                    price = float(price_text)
                    data.append([time_text, price])
                except ValueError:
                    continue

        df = pd.DataFrame(data, columns=["Time", "Price"])
        df["Price"] = df["Price"].astype(float)
        return df

    except Exception as e:
        print(f"❌ 發生錯誤：{e}")
        return pd.DataFrame(columns=["Time", "Price"])

# 計算布林通道
def compute_bollinger(df, period=20, num_std=2):
    df["MA"] = df["Price"].rolling(period).mean()
    df["STD"] = df["Price"].rolling(period).std()
    df["Upper"] = df["MA"] + num_std * df["STD"]
    df["Lower"] = df["MA"] - num_std * df["STD"]
    return df

# 判斷是否突破布林通道並發送通知
def check_and_notify(df):
    latest = df.iloc[-1]
    price = latest["Price"]
    upper = latest["Upper"]
    lower = latest["Lower"]

    print(f"🔍 時間：{latest['Time']}｜價格：{price}｜上緣：{upper:.2f}｜下緣：{lower:.2f}")

    if price > upper:
        msg = f"📈 價格突破布林通道上緣！\n價格：{price}\n上緣：{upper:.2f}"
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)
        print("📤 已發送突破上緣通知")
    elif price < lower:
        msg = f"📉 價格跌破布林通道下緣！\n價格：{price}\n下緣：{lower:.2f}"
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)
        print("📤 已發送跌破下緣通知")

# 主循環執行緒
def monitor():
    global history_df

    while True:
        df = fetch_price()
        if not df.empty:
            # 合併歷史資料並移除重複時間點
            history_df = pd.concat([history_df, df]).drop_duplicates(subset="Time", keep="last")

            if len(history_df) >= 20:
                temp_df = compute_bollinger(history_df.copy())
                check_and_notify(temp_df)

        time.sleep(5)

# 網頁根目錄提供 keep-alive ping
@app.route("/", methods=["GET", "HEAD"])
def home():
    return "✅ 台指期布林通道監控正常執行中"

# 啟動監控執行緒
if __name__ == "__main__":
    threading.Thread(target=monitor).start()
    app.run(host="0.0.0.0", port=10000)
