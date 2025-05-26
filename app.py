from flask import Flask
import requests
import pandas as pd
import time
import threading
import telegram
from datetime import datetime
from bs4 import BeautifulSoup

app = Flask(__name__)

# Telegram bot 設定
TELEGRAM_TOKEN = '你的 TELEGRAM BOT TOKEN'
TELEGRAM_CHAT_ID = '你的 CHAT_ID'
bot = telegram.Bot(token=TELEGRAM_TOKEN)

last_signal = None  # 避免重複發送

def fetch_txf_data():
    try:
        url = "https://tw.stock.yahoo.com/futures/real"  # 網址為即時期貨報價
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, "lxml")
        price_tag = soup.find("span", {"data-test": "qsp-price"})
        if price_tag:
            return float(price_tag.text.replace(',', ''))
        else:
            print("找不到價格")
            return None
    except Exception as e:
        print(f"❌ 發生錯誤：{e}")
        return None

def check_bollinger():
    global last_signal
    prices = []

    while True:
        price = fetch_txf_data()
        if price:
            prices.append(price)

            # 保留最後 20 筆價格計算布林通道
            if len(prices) > 20:
                prices = prices[-20:]

                df = pd.DataFrame(prices, columns=["price"])
                df["MA20"] = df["price"].rolling(window=20).mean()
                df["STD"] = df["price"].rolling(window=20).std()
                df["Upper"] = df["MA20"] + 2 * df["STD"]
                df["Lower"] = df["MA20"] - 2 * df["STD"]

                current = df["price"].iloc[-1]
                upper = df["Upper"].iloc[-1]
                lower = df["Lower"].iloc[-1]

                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                if current > upper and last_signal != "high":
                    bot.send_message(chat_id=TELEGRAM_CHAT_ID,
                                     text=f"📈 台指期突破上軌！\n時間：{now}\n價格：{current}")
                    last_signal = "high"
                elif current < lower and last_signal != "low":
                    bot.send_message(chat_id=TELEGRAM_CHAT_ID,
                                     text=f"📉 台指期跌破下軌！\n時間：{now}\n價格：{current}")
                    last_signal = "low"
                elif lower <= current <= upper:
                    last_signal = None  # 回到正常狀態，下次突破會再通知

        time.sleep(5)

@app.route('/')
def index():
    return '台指期布林通道機器人運作中'

def start_monitor():
    t = threading.Thread(target=check_bollinger)
    t.daemon = True
    t.start()

if __name__ == '__main__':
    start_monitor()
    app.run(host="0.0.0.0", port=10000)
