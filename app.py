import pandas as pd
import requests
import time
import threading
import telegram
from flask import Flask
from datetime import datetime

# Telegram 設定
TELEGRAM_TOKEN = '7863895518:AAH0avbUgC_yd7RoImzBvQJXFmIrKXjuSj8'
TELEGRAM_CHAT_ID = '1190387445'
bot = telegram.Bot(token=TELEGRAM_TOKEN)

# Flask 伺服器
app = Flask(__name__)

@app.route('/')
def index():
    return 'OK'

@app.route('/keep-alive')
def keep_alive():
    return 'I am alive', 200

# Yahoo 期貨近月一網址
URL = 'https://tw.stock.yahoo.com/future/futures-chart/WTX1?guccounter=1'

# 儲存歷史資料
history = []

# 發送通知紀錄
notified = {"upper": False, "lower": False}

def fetch_data():
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(URL, headers=headers)
        tables = pd.read_html(r.text)
        df = tables[1]  # 第 2 張表是 1 分 K

        df.columns = ['時間', '成交', '漲跌', '買價', '賣價', '單量', '總量']
        df = df[['時間', '成交']]
        df = df.dropna()
        df['時間'] = pd.to_datetime(df['時間'])
        df['成交'] = pd.to_numeric(df['成交'], errors='coerce')
        df = df.dropna()

        return df
    except Exception as e:
        print("❌ 發生錯誤：", e)
        return None

def check_bollinger():
    global history, notified
    while True:
        df = fetch_data()
        if df is not None and not df.empty:
            history.extend(df.to_dict('records'))

            # 保留最近 60 筆資料（約 1 小時）
            history = history[-60:]

            hist_df = pd.DataFrame(history)
            hist_df['成交'] = pd.to_numeric(hist_df['成交'])

            if len(hist_df) >= 20:
                close = hist_df['成交']
                ma = close.rolling(window=20).mean()
                std = close.rolling(window=20).std()
                upper = ma + 2 * std
                lower = ma - 2 * std
                latest = close.iloc[-1]

                print(f"[{datetime.now().strftime('%H:%M:%S')}] 現價: {latest:.2f}, 上緣: {upper.iloc[-1]:.2f}, 下緣: {lower.iloc[-1]:.2f}")

                if latest > upper.iloc[-1]:
                    if not notified["upper"]:
                        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f"🚨 台指期價格突破布林通道上緣！現價：{latest:.2f}")
                        notified = {"upper": True, "lower": False}
                elif latest < lower.iloc[-1]:
                    if not notified["lower"]:
                        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f"⚠️ 台指期價格跌破布林通道下緣！現價：{latest:.2f}")
                        notified = {"upper": False, "lower": True}
                else:
                    notified = {"upper": False, "lower": False}

        time.sleep(5)

# 背景啟動
def start_monitor():
    thread = threading.Thread(target=check_bollinger)
    thread.daemon = True
    thread.start()

# 指定 Port 綁定
if __name__ == '__main__':
    start_monitor()
    import os
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
