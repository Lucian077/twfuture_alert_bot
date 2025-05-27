import os
import requests
import time
import pandas as pd
import numpy as np
from datetime import datetime, time as dt_time
import pytz
import logging
from flask import Flask, Response

# 設定台灣時區
taipei_tz = pytz.timezone('Asia/Taipei')

# 初始化 Flask 應用
app = Flask(__name__)

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 環境變數設定 (在 Render 後台設定)
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
YAHOO_SYMBOL = os.getenv('YAHOO_SYMBOL', 'WTX=F')  # 台指期近月

# 交易時段設定 (全天候監控，但仍區分日盤/夜盤標記)
DAY_TRADE_START = dt_time(8, 45)  # 日盤開始
DAY_TRADE_END = dt_time(13, 45)    # 日盤結束
NIGHT_TRADE_START = dt_time(15, 0) # 夜盤開始
NIGHT_TRADE_END = dt_time(5, 0)    # 夜盤結束 (次日凌晨)

# 布林通道設定
BOLLINGER_PERIOD = 20
BOLLINGER_STD = 2
CHECK_INTERVAL = 5  # 秒

class TXFMonitor:
    def __init__(self):
        self.historical_data = []
        self.last_alert_time = None
        self.alert_cooldown = 300  # 相同方向警報冷卻時間(秒)
        self.last_price = None
        self.last_update_time = None
        
    def is_day_trading_hours(self):
        """檢查當前是否為日盤交易時段"""
        now = datetime.now(taipei_tz)
        current_time = now.time()
        current_weekday = now.weekday()  # 0=周一, 6=周日
        
        # 週一至週五日盤 (08:45~13:45)
        if current_weekday < 5 and DAY_TRADE_START <= current_time <= DAY_TRADE_END:
            return True
        return False
    
    def is_night_trading_hours(self):
        """檢查當前是否為夜盤交易時段"""
        now = datetime.now(taipei_tz)
        current_time = now.time()
        current_weekday = now.weekday()
        
        # 週一至週五夜盤 (15:00~次日05:00)
        if current_weekday < 5:  # 週一至週五
            if current_time >= NIGHT_TRADE_START or current_time < NIGHT_TRADE_END:
                return True
        
        # 週六凌晨 (00:00~05:00) 視為週五夜盤延續
        if current_weekday == 5 and current_time < NIGHT_TRADE_END:
            return True
            
        return False
    
    def get_market_session(self):
        """取得當前市場時段標籤"""
        if self.is_day_trading_hours():
            return "日盤"
        elif self.is_night_trading_hours():
            return "夜盤"
        return "非交易時段"
    
    def get_txf_price(self):
        """從 Yahoo Finance 獲取台指期價格"""
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{YAHOO_SYMBOL}?interval=1m"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            data = response.json()
            
            if "chart" not in data or "result" not in data["chart"]:
                logger.error("Yahoo API 返回無效數據")
                return None
                
            meta = data["chart"]["result"][0]["meta"]
            latest_price = meta["regularMarketPrice"]
            latest_time = meta["regularMarketTime"]
            
            return {
                'timestamp': latest_time,
                'close': latest_price
            }
        except Exception as e:
            logger.error(f"獲取價格失敗: {e}")
            return None
    
    def calculate_bollinger_bands(self, data):
        """計算布林通道"""
        df = pd.DataFrame(data[-BOLLINGER_PERIOD:])
        df['MA'] = df['close'].rolling(window=BOLLINGER_PERIOD).mean()
        df['STD'] = df['close'].rolling(window=BOLLINGER_PERIOD).std()
        df['Upper'] = df['MA'] + (df['STD'] * BOLLINGER_STD)
        df['Lower'] = df['MA'] - (df['STD'] * BOLLINGER_STD)
        return df.iloc[-1]
    
    def send_telegram_alert(self, message):
        """發送 Telegram 通知"""
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        try:
            requests.post(url, json={
                'chat_id': TELEGRAM_CHAT_ID,
                'text': message,
                'parse_mode': 'Markdown'
            })
            logger.info("Telegram通知已發送")
        except Exception as e:
            logger.error(f"發送Telegram通知失敗: {e}")
    
    def check_breakout(self):
        """檢查布林通道突破"""
        latest_data = self.get_txf_price()
        if not latest_data:
            return False
        
        # 檢查價格是否有更新
        if self.last_price == latest_data['close'] and self.last_update_time == latest_data['timestamp']:
            logger.info("價格未更新，跳過檢查")
            return False
            
        self.last_price = latest_data['close']
        self.last_update_time = latest_data['timestamp']
        
        self.historical_data.append(latest_data)
        if len(self.historical_data) > BOLLINGER_PERIOD * 2:
            self.historical_data.pop(0)
        
        # 確保有足夠數據計算
        if len(self.historical_data) < BOLLINGER_PERIOD:
            return False
            
        bb = self.calculate_bollinger_bands(self.historical_data)
        current_price = latest_data['close']
        timestamp = datetime.fromtimestamp(latest_data['timestamp'], taipei_tz)
        market_session = self.get_market_session()
        
        logger.info(f"時間: {timestamp.strftime('%Y-%m-%d %H:%M:%S')} ({market_session})")
        logger.info(f"當前價格: {current_price}")
        logger.info(f"布林通道: {bb['Upper']:.2f} | {bb['MA']:.2f} | {bb['Lower']:.2f}")
        
        alert_msg = None
        if current_price > bb['Upper']:
            alert_msg = f"*⚠️ 突破布林上軌!* ({market_session})\n時間: {timestamp.strftime('%H:%M:%S')}\n價格: `{current_price}`\n上軌: `{bb['Upper']:.2f}`"
        elif current_price < bb['Lower']:
            alert_msg = f"*⚠️ 突破布林下軌!* ({market_session})\n時間: {timestamp.strftime('%H:%M:%S')}\n價格: `{current_price}`\n下軌: `{bb['Lower']:.2f}`"
        
        if alert_msg:
            # 檢查警報冷卻時間
            if self.last_alert_time and (time.time() - self.last_alert_time) < self.alert_cooldown:
                logger.info("警報冷卻中，暫不發送")
            else:
                self.send_telegram_alert(alert_msg)
                self.last_alert_time = time.time()
            return True
        return False
    
    def run_monitor(self):
        """主監控循環"""
        logger.info("=== 台指期全天候監控系統啟動 ===")
        
        # 初始化歷史數據
        while len(self.historical_data) < BOLLINGER_PERIOD:
            price_data = self.get_txf_price()
            if price_data:
                self.historical_data.append(price_data)
            time.sleep(1)
        
        logger.info("歷史數據初始化完成，開始全天候監控...")
        
        while True:
            try:
                market_session = self.get_market_session()
                logger.info(f"當前市場時段: {market_session}")
                
                self.check_breakout()
                    
                time.sleep(CHECK_INTERVAL)
            except Exception as e:
                logger.error(f"監控循環錯誤: {e}")
                time.sleep(60)  # 錯誤後等待1分鐘再重試

# 初始化監控器
monitor = TXFMonitor()

# Flask 路由 (供 UptimeRobot 監控用)
@app.route('/')
def health_check():
    return Response("台指期全天候監控系統運行中", status=200)

@app.route('/start_monitor')
def start_monitor():
    # 在 Render 上啟動監控
    import threading
    monitor_thread = threading.Thread(target=monitor.run_monitor)
    monitor_thread.daemon = True
    monitor_thread.start()
    return Response("監控已啟動", status=200)

if __name__ == '__main__':
    # 本地運行直接啟動監控
    monitor.run_monitor()
