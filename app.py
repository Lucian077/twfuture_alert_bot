import os
import requests
import time
import pandas as pd
import numpy as np
from datetime import datetime, time as dt_time
import pytz
import logging
from flask import Flask, Response

# 初始化 Flask 应用 (必须放在最前面)
app = Flask(__name__)

# 配置端口 (Render 需要)
PORT = int(os.environ.get("PORT", 10000))

# 设置台湾时区
taipei_tz = pytz.timezone('Asia/Taipei')

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 环境变量配置
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
YAHOO_SYMBOL = os.getenv('YAHOO_SYMBOL', 'WTX=F')

# 使用更可靠的 yfinance 替代 Yahoo API
try:
    import yfinance as yf
    USE_YFINANCE = True
except ImportError:
    USE_YFINANCE = False
    logger.warning("yfinance 未安装，将使用 Yahoo API")

class TXFMonitor:
    def __init__(self):
        self.historical_data = []
        self.ticker = yf.Ticker(YAHOO_SYMBOL) if USE_YFINANCE else None
        self.last_alert_time = None
        self.alert_cooldown = 300  # 5分钟冷却时间
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def get_txf_price(self):
        """获取台指期价格 (使用 yfinance 或 Yahoo API)"""
        try:
            if USE_YFINANCE:
                data = self.ticker.history(period='1d', interval='1m')
                if not data.empty:
                    latest = data.iloc[-1]
                    return {
                        'timestamp': latest.name.timestamp(),
                        'close': latest['Close']
                    }
            else:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{YAHOO_SYMBOL}?interval=1m"
                response = self.session.get(url, timeout=10)
                data = response.json()
                
                if data.get('chart', {}).get('result'):
                    meta = data['chart']['result'][0]['meta']
                    return {
                        'timestamp': meta['regularMarketTime'],
                        'close': meta['regularMarketPrice']
                    }
        except Exception as e:
            logger.error(f"获取价格失败: {str(e)}")
        return None

    # 保持其他方法不变 (calculate_bollinger_bands, send_telegram_alert, check_breakout 等)

# 初始化监控器
monitor = TXFMonitor()

@app.route('/')
def health_check():
    return Response("台指期监控系统运行中", status=200)

@app.route('/start_monitor')
def start_monitor():
    import threading
    if not hasattr(app, 'monitor_thread'):
        app.monitor_thread = threading.Thread(target=monitor.run_monitor)
        app.monitor_thread.daemon = True
        app.monitor_thread.start()
    return Response("监控已启动", status=200)

if __name__ == '__main__':
    # 启动Flask服务
    from waitress import serve
    serve(app, host="0.0.0.0", port=PORT)
