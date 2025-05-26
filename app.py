import requests
import pandas as pd
import time
import telegram
from datetime import datetime
from flask import Flask

# Telegram 設定
TELEGRAM_TOKEN = '7863895518:AAH0avbUgC_yd7RoImzBvQJXFmIrKXjuSj8'
TELEGRAM_CHAT_ID = '1190387445'
bot = telegram.Bot(token=TELEGRAM_TOKEN)

# Yahoo 期貨資料網址（台指期近月一）
YAHOO_URL = 'https://tw.screener.finance.yahoo.net/future/chartDataList.html?symbol=WTX&contractId=WTX&duration=1m'

# 初始化 Flask App（用來保持 Render 運作）
app = Flask(__name__)

@app.route('/')
def index():
    return '服務正常運作中'

def fetch_kline():
    """從 Yahoo 擷取 1 分鐘 K 線資料"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0'
        }
        response = requests.get(YAHOO_URL, headers=headers)
        raw_data = response.json()
        data = raw_data[0]['data']
        df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms') + pd.Timedelta(hours=8)
        df.set_index('timestamp', inplace=True)
        return df
    except Exception as e:
        print(f"❌ 發生錯誤：{e}")
        return None

def calculate_bollinger(df, period=20, num_std=2):
    """計算布林通道"""
    df['MA'] = df['close'].rolling(window=period).mean()
    df['STD'] = df['close'].rolling(window=period).std()
    df['Upper'] = df['MA'] + num_std * df['STD']
    df['Lower'] = df['MA'] - num_std * df['STD']
    return df

def monitor_bollinger():
    print("📈 開始監控台指期布林通道（含夜盤）...")
    notified = {'upper': False, 'lower': False}

    while True:
        df = fetch_kline()
        if df is None or len(df) < 20:
            time.sleep(5)
            continue

        df = calculate_bollinger(df)
        latest = df.iloc[-1]

        price = latest['close']
        upper = latest['Upper']
        lower = latest['Lower']
        timestamp = latest.name.strftime('%Y-%m-%d %H:%M:%S')

        message = None

        if price > upper:
            if not notified['upper']:
                message = f"📢 {timestamp} 台指期突破【布林上緣】\n現價：{price:.2f} > 上緣：{upper:.2f}"
                notified['upper'] = True
                notified['lower'] = False
        elif price < lower:
            if not notified['lower']:
                message = f"📢 {timestamp} 台指期跌破【布林下緣】\n現價：{price:.2f} < 下緣：{lower:.2f}"
                notified['lower'] = True
                notified['upper'] = False
        else:
            notified = {'upper': False, 'lower': False}

        if message:
            try:
                bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
                print(f"✅ 已通知：{message}")
            except Exception as e:
                print(f"❌ Telegram 發送失敗：{e}")

        time.sleep(5)

if __name__ == '__main__':
    import threading
    t = threading.Thread(target=monitor_bollinger)
    t.daemon = True
    t.start()

    import os
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
