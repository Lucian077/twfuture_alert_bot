import pandas as pd
import requests
import telegram
import time
from flask import Flask

# ===== Telegram 設定 =====
TELEGRAM_TOKEN = '7863895518:AAH0avbUgC_yd7RoImzBvQJXFmIrKXjuSj8'
TELEGRAM_CHAT_ID = '1190387445'
bot = telegram.Bot(token=TELEGRAM_TOKEN)

# ===== Flask keep-alive 設定 =====
app = Flask(__name__)
@app.route('/')
def index():
    return 'Bot is running'

# ===== Yahoo 台指期近月一資料爬蟲網址（1分K） =====
YAHOO_URL = "https://tw.stock.yahoo.com/_td-stock/api/resource/FinanceChartService;type=minute;range=1d;symbol=WTXF1.TW"

# ===== 初始歷史資料（最多補20筆） =====
def get_kline_data():
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    res = requests.get(YAHOO_URL, headers=headers)
    data = res.json()
    prices = data['chart']['result'][0]['indicators']['quote'][0]['close']
    times = data['chart']['result'][0]['timestamp']

    df = pd.DataFrame({'time': pd.to_datetime(times, unit='s'), 'close': prices})
    df = df.dropna()
    return df.tail(20)

# ===== 計算布林通道 =====
def calc_bollinger(df):
    df['MA20'] = df['close'].rolling(window=20).mean()
    df['STD'] = df['close'].rolling(window=20).std()
    df['Upper'] = df['MA20'] + 2 * df['STD']
    df['Lower'] = df['MA20'] - 2 * df['STD']
    return df

# ===== 判斷是否突破布林通道 =====
last_notified = None
def check_breakout():
    global last_notified
    try:
        df = get_kline_data()
        df = calc_bollinger(df)
        latest = df.iloc[-1]

        if latest['close'] > latest['Upper']:
            msg = f"🚀 台指期突破上緣！\n價格：{latest['close']:.2f}"
        elif latest['close'] < latest['Lower']:
            msg = f"🔻 台指期跌破下緣！\n價格：{latest['close']:.2f}"
        else:
            return

        if last_notified != msg:
            bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)
            last_notified = msg

    except Exception as e:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f"❌ 發生錯誤：{e}")

# ===== 每 5 秒監控一次 =====
def start_monitor():
    while True:
        check_breakout()
        time.sleep(5)

# ===== 開始 Flask 與監控 =====
if __name__ == '__main__':
    import threading
    t = threading.Thread(target=start_monitor)
    t.daemon = True
    t.start()
    app.run(host='0.0.0.0', port=10000)
