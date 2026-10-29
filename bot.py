import ccxt
import pandas as pd
import requests
import xml.etree.ElementTree as ET
import time
import json
import os
import sys
from datetime import datetime
from google import genai

# ==========================================
# ১. কনফিগারেশন
# ==========================================
GEMINI_API_KEY = "AQ.Ab8RN6J1jm_pMdnfeyd9zXEkMjmYxBpwEJ2QeWJsrhPTS_AN-A"
SYMBOL = 'BTC/USDT'
BUY_RSI_THRESHOLD = 40.0   
TAKE_PROFIT_PCT = 2.0      
STOP_LOSS_PCT = -3.0       
CHECK_INTERVAL = 60        

exchange = ccxt.binance({'options': {'defaultType': 'spot'}})
ai_client = genai.Client(api_key=GEMINI_API_KEY)
PORTFOLIO_FILE = "paper_portfolio.json"

# ==========================================
# ২. ভার্চুয়াল ওয়ালেট (Smart DCA Portfolio)
# ==========================================
def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, 'r') as f:
            return json.load(f)
    return {
        "usdt_balance": 100.0, 
        "btc_amount": 0.0, 
        "avg_buy_price": 0.0, 
        "dca_step": 0,  # ৩ ধাপে কেনার হিসাব রাখবে
        "total_trades": 0, 
        "wins": 0
    }

def save_portfolio(data):
    with open(PORTFOLIO_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# ==========================================
# ৩. মার্কেট ডেটা (Cloud 451 Fallback)
# ==========================================
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_market_data(symbol):
    try:
        bars = exchange.fetch_ohlcv(symbol, timeframe='1h', limit=50)
        df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['rsi'] = calculate_rsi(df['close'])
        return df['close'].iloc[-1], df['rsi'].iloc[-1]
    except Exception:
        url = "https://api.binance.us/api/v3/klines?symbol=BTCUSDT&interval=1h&limit=50"
        res = requests.get(url, timeout=10).json()
        closes = [float(k[4]) for k in res]
        df = pd.DataFrame({'close': closes})
        df['rsi'] = calculate_rsi(df['close'])
        return float(closes[-1]), float(df['rsi'].iloc[-1])

# ==========================================
# ৪. Smart AI Brain (Auto-Fallback & Cache)
# ==========================================
last_ai_check_time = 0
cached_ai_status = "SAFE"
cached_ai_reason = "Initial check pending..."

def get_live_news():
    url = "https://www.coindesk.com/arc/outboundfeeds/rss/"
    response = requests.get(url, timeout=10)
    root = ET.fromstring(response.content)
    return [item.find('title').text for item in root.findall('./channel/item')[:3]]

def analyze_news_with_ai(headlines):
    global last_ai_check_time, cached_ai_status, cached_ai_reason
    if time.time() - last_ai_check_time < 900 and last_ai_check_time != 0:
        return cached_ai_status, f"(Cached) {cached_ai_reason}"

    prompt = f"""
    You are a professional halal crypto spot trading risk manager.
    Analyze these latest news headlines:
    {headlines}
    Is there any severe market crash, major exchange hack, global war escalation, or crypto ban happening right now?
    Respond in this exact format:
    STATUS: [SAFE or DANGER]
    REASON: [1 short sentence explaining why]
    """
    try:
        response = ai_client.models.generate_content(
            model='gemini-3.8-flash',
            contents=prompt,
        )
        text = response.text.strip()
        cached_ai_status = "DANGER" if "STATUS: DANGER" in text.upper() else "SAFE"
        cached_ai_reason = text.split("REASON:")[-1].strip() if "REASON:" in text else text
        last_ai_check_time = time.time()
        return cached_ai_status, cached_ai_reason
    except Exception:
        danger_words = ['hacked', 'market crash', 'crypto ban', 'world war', 'bankrupt']
        for news in headlines:
            for w in danger_words:
                if w in news.lower():
                    return "DANGER", f"Backup shield detected '{w}' in news!"
        return "SAFE", "Backup news scanner confirmed headlines are normal."

# ==========================================
# ৫. ২৪/৭ মেইন ট্রেডিং ইঞ্জিন (Smart DCA)
# ==========================================
def run_bot_cycle():
    portfolio = load_portfolio()
    price, rsi = get_market_data(SYMBOL)
    news_list = get_live_news()
    ai_status, ai_reason = analyze_news_with_ai(news_list)

    print("\n" + "=" * 65)
    print(f"🤖 PRO HALAL AI BOT (SMART DCA) | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 65)
    print(f"💼 Wallet: ${portfolio['usdt_balance']:.2f} USDT | {portfolio['btc_amount']:.6f} BTC")
    print(f"📊 {SYMBOL} Price: ${price:,.2f} | RSI (1h): {rsi:.2f}")
    print("-" * 65)
    print(f"🧠 AI News Verdict: [{ai_status}] -> {ai_reason}")
    print("-" * 65)

    # Smart DCA কেনার লজিক (সর্বোচ্চ ৩ বার কিনবে)
    if portfolio['dca_step'] < 3:
        if rsi < BUY_RSI_THRESHOLD and ai_status == "SAFE":
            # ১০০ ডলারকে ৩ ভাগ করে কিনবে (৩৩.৩৩ ডলার করে)
            step_amount = 33.33
            if portfolio['dca_step'] == 2 or portfolio['usdt_balance'] < 35.0:
                step_amount = portfolio['usdt_balance'] # শেষ ধাপে বাকি সবটুকু দিয়ে কিনবে
            
            if step_amount > 5:
                btc_bought = step_amount / price
                total_spent_before = portfolio['avg_buy_price'] * portfolio['btc_amount']
                new_total_btc = portfolio['btc_amount'] + btc_bought
                
                # নতুন গড় দাম হিসাব করা
                portfolio['avg_buy_price'] = (total_spent_before + step_amount) / new_total_btc
                portfolio['btc_amount'] = new_total_btc
                portfolio['usdt_balance'] -= step_amount
                portfolio['dca_step'] += 1
                
                save_portfolio(portfolio)
                print(f"🟢 DCA STEP {portfolio['dca_step']}/3 EXECUTED! Bought ${step_amount:.2f} at ${price:,.2f}")
        else:
            print(f"⏳ WAITING FOR DCA ENTRY: Need RSI < {BUY_RSI_THRESHOLD} (Current: {rsi:.2f})")

    # প্রফিট বা লস হিসাব করে বিক্রির লজিক
    if portfolio['btc_amount'] > 0:
        avg_price = portfolio['avg_buy_price']
        profit_pct = ((price - avg_price) / avg_price) * 100
        current_value = portfolio['btc_amount'] * price
        
        print(f"📈 Open Trade (DCA {portfolio['dca_step']}/3): Avg Buy Price ${avg_price:,.2f}")
        print(f"💰 Current P/L: {profit_pct:+.2f}% (${current_value:.2f})")

        if profit_pct >= TAKE_PROFIT_PCT:
            portfolio['usdt_balance'] += current_value
            portfolio['btc_amount'] = 0.0
            portfolio['dca_step'] = 0
            portfolio['avg_buy_price'] = 0.0
            portfolio['total_trades'] += 1
            portfolio['wins'] += 1
            save_portfolio(portfolio)
            print(f"🎯 TAKE PROFIT! Sold all BTC for ${current_value:.2f} (+{profit_pct:.2f}% Profit!)")

        elif profit_pct <= STOP_LOSS_PCT or ai_status == "DANGER":
            portfolio['usdt_balance'] += current_value
            portfolio['btc_amount'] = 0.0
            portfolio['dca_step'] = 0
            portfolio['avg_buy_price'] = 0.0
            portfolio['total_trades'] += 1
            save_portfolio(portfolio)
            print(f"🛑 EMERGENCY SELL! Sold all BTC for ${current_value:.2f}")

    print("=" * 65)

if __name__ == "__main__":
    if not os.path.exists(PORTFOLIO_FILE):
        save_portfolio(load_portfolio())
        print("📁 Created 'paper_portfolio.json' with $100.00 starting balance!")

    if "--once" in sys.argv:
        print("☁️ Running Single Cloud Check...")
        run_bot_cycle()
    else:
        print("🚀 Starting 24/7 Local Halal AI Bot... (Press Ctrl+C to stop)")
        while True:
            try:
                run_bot_cycle()
                time.sleep(CHECK_INTERVAL)
            except KeyboardInterrupt:
                print("\n🛑 Bot stopped by user.")
                break
            except Exception as e:
                print(f"⚠️ Connection error: {e}. Retrying in 30 seconds...")
                time.sleep(30)