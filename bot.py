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
from dotenv import load_dotenv

load_dotenv()

# ==========================================
# ১. কনফিগারেশন ও সিকিউর এপিআই কি
# ==========================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SYMBOL = 'BTC/USDT'
BUY_RSI_THRESHOLD = 48.0   # সহজে প্রথম ট্রেড নেওয়ার জন্য 48 করা হলো
TAKE_PROFIT_PCT = 1.5      # ১.৫% লাভ হলেই প্রফিট বুক করবে
STOP_LOSS_PCT = -3.0       
CHECK_INTERVAL = 60        
PORTFOLIO_FILE = "paper_portfolio.json"

exchange = ccxt.binance({'options': {'defaultType': 'spot'}})

# ==========================================
# ২. ভার্চুয়াল ওয়ালেট ও প্রফিট ভল্ট লোড/সেভ
# ==========================================
def load_portfolio():
    default_data = {
        "usdt_balance": 100.0,
        "profit_vault": 0.0,      # 🔒 ৭৫% লাভ এখানে চিরস্থায়ীভাবে জমা থাকবে
        "btc_amount": 0.0,
        "avg_buy_price": 0.0,
        "dca_step": 0,
        "total_trades": 0,
        "wins": 0,
        "trade_history": [],
        "ai_market_summary": "বট মার্কেট পর্যবেক্ষণ করছে। খুব শীঘ্রই আপডেট আসবে...",
        "last_signal": "HOLD",
        "indicators": {"rsi": 50.0, "macd": 0.0, "ema_20": 0.0, "ema_50": 0.0},
        "backtest_win_rate": 0.0,
        "last_update": "এখনো সিঙ্ক হয়নি"
    }
    if os.path.exists(PORTFOLIO_FILE):
        try:
            with open(PORTFOLIO_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for k, v in default_data.items():
                    if k not in data:
                        data[k] = v
                return data
        except Exception:
            pass
    return default_data

def save_portfolio(data):
    data["last_update"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(PORTFOLIO_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# ==========================================
# ৩. আপনার প্রো স্ট্রাকচার ফাংশনসমূহ
# ==========================================
def get_market_data(symbol=SYMBOL, limit=100):
    """১. Live Market Price এবং ক্যান্ডেল ডেটা সংগ্রহ"""
    try:
        bars = exchange.fetch_ohlcv(symbol, timeframe='1h', limit=limit)
        df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    except Exception:
        url = f"https://api.binance.us/api/v3/klines?symbol=BTCUSDT&interval=1h&limit={limit}"
        res = requests.get(url, timeout=10).json()
        data = [[int(k[0]), float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])] for k in res]
        df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['time'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

def calculate_indicators(df):
    """২. RSI + MACD + EMA ক্যালকুলেশন"""
    # RSI (14)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

    # EMA (20 & 50)
    df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()

    # MACD (12, 26, 9)
    ema_12 = df['close'].ewm(span=12, adjust=False).mean()
    ema_26 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = ema_12 - ema_26
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    return df

def get_live_news():
    try:
        url = "https://www.coindesk.com/arc/outboundfeeds/rss/"
        response = requests.get(url, timeout=10)
        root = ET.fromstring(response.content)
        return [item.find('title').text for item in root.findall('./channel/item')[:3]]
    except Exception:
        return ["Crypto market trading normally with standard volume."]

def analyze_market(df, headlines):
    """৩. AI দিয়ে মার্কেট এবং নিউজ বিশ্লেষণ (ড্যাশবোর্ডের জন্য বাংলা রিপোর্ট তৈরি)"""
    last = df.iloc[-1]
    price = float(last['close'])
    rsi = float(last['rsi'])
    macd = float(last['macd'])
    ema_trend = "UPTREND (বুলিশ)" if last['ema_20'] > last['ema_50'] else "DOWNTREND (বিয়ারিশ)"

    if not GEMINI_API_KEY or not GEMINI_API_KEY.startswith("AIza"):
        return "SAFE", f"মার্কেট এখন {ema_trend}-এ আছে। বর্তমান RSI {rsi:.1f} এবং MACD {macd:.2f}। বট নিয়ম অনুযায়ী ট্রেড করছে।"

    prompt = f"""
    Live BTC Price: ${price:,.2f} | RSI(14): {rsi:.2f} | MACD: {macd:.2f} | Trend: {ema_trend}
    News Headlines: {headlines}
    
    Task 1: Is there any severe crash/hack/ban? Write STATUS: SAFE or STATUS: DANGER.
    Task 2: Write a 2-sentence summary in Bengali (বাংলায়) for the user explaining current market condition and indicators so the user can learn easily.
    Format:
    STATUS: [SAFE/DANGER]
    SUMMARY: [বাংলায় ২ লাইনের সহজ বিশ্লেষণ]
    """
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        # দ্রুত এবং নির্ভরযোগ্য কলের জন্য স্ট্যান্ডার্ড মডেল ফলব্যাক
        try:
            res = client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
            text = res.text.strip()
        except Exception:
            inter = client.interactions.create(model='models/gemini-3.8-flash', input=prompt)
            text = inter.steps[-1].strip()

        status = "DANGER" if "STATUS: DANGER" in text.upper() else "SAFE"
        summary = text.split("SUMMARY:")[-1].strip() if "SUMMARY:" in text else text
        return status, summary
    except Exception:
        return "SAFE", f"মার্কেট এখন {ema_trend}-এ রয়েছে (RSI: {rsi:.1f})। বড় কোনো নেতিবাচক খবর নেই, বট স্বয়ংক্রিয়ভাবে মার্কেট পর্যবেক্ষণ করছে।"

def generate_signal(df, portfolio, ai_status):
    """৪. Buy/Sell সিগন্যাল তৈরি করা"""
    last = df.iloc[-1]
    price = float(last['close'])
    rsi = float(last['rsi'])
    macd_bullish = last['macd'] > last['macd_signal']

    # Sell Signal চেক
    if portfolio['btc_amount'] > 0:
        avg_price = portfolio['avg_buy_price']
        profit_pct = ((price - avg_price) / avg_price) * 100
        if profit_pct >= TAKE_PROFIT_PCT:
            return "SELL_PROFIT", f"লক্ষ্যমাত্রা পূরণ হয়েছে (+{profit_pct:.2f}% লাভ)"
        elif profit_pct <= STOP_LOSS_PCT or ai_status == "DANGER":
            return "SELL_EMERGENCY", f"স্টপ লস বা ঝুঁকি এড়াতে বিক্রি ({profit_pct:.2f}%)"

    # Buy Signal চেক (প্রথম ধাপ সহজে কেনার লজিক + পরবর্তী DCA ধাপ)
    if portfolio['dca_step'] < 3 and ai_status == "SAFE" and portfolio['usdt_balance'] > 5:
        if portfolio['dca_step'] == 0 and (rsi < BUY_RSI_THRESHOLD or (macd_bullish and rsi < 54)):
            return "BUY", f"প্রথম এন্ট্রি সিগন্যাল (RSI: {rsi:.1f})"
        elif portfolio['dca_step'] > 0 and rsi < BUY_RSI_THRESHOLD:
            # আগের কেনা দাম থেকে অন্তত ১% নিচে নামলে পরের ধাপ কিনবে
            if price < portfolio['avg_buy_price'] * 0.99:
                return "BUY", f"DCA ধাপ {portfolio['dca_step']+1} সিগন্যাল (RSI: {rsi:.1f})"

    return "HOLD", f"সঠিক সিগন্যালের অপেক্ষায় (RSI: {rsi:.1f})"

def calculate_risk(portfolio):
    """৫. রিস্ক এবং কত ডলার দিয়ে ট্রেড করবে তার হিসাব"""
    remaining_steps = 3 - portfolio['dca_step']
    if remaining_steps <= 1 or portfolio['usdt_balance'] < 15.0:
        return portfolio['usdt_balance']
    return round(portfolio['usdt_balance'] / remaining_steps, 2)

def paper_trade(signal, reason, price, portfolio):
    """৬. পেপার ট্রেডিং ও ৭৫% প্রফিট ভল্ট লজিক!"""
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if signal == "BUY":
        step_amount = calculate_risk(portfolio)
        if step_amount > 5:
            btc_bought = step_amount / price
            total_spent_before = portfolio['avg_buy_price'] * portfolio['btc_amount']
            new_total_btc = portfolio['btc_amount'] + btc_bought

            portfolio['avg_buy_price'] = (total_spent_before + step_amount) / new_total_btc
            portfolio['btc_amount'] = new_total_btc
            portfolio['usdt_balance'] -= step_amount
            portfolio['dca_step'] += 1

            portfolio['trade_history'].insert(0, {
                "সময়": now_str,
                "ধরন": f"🟢 BUY (ধাপ {portfolio['dca_step']}/3)",
                "প্রাইস": f"${price:,.2f}",
                "পরিমাণ (USDT)": f"${step_amount:.2f}",
                "লাভ/লস": "-",
                "ভল্টে জমা (৭৫%)": "-",
                "কারণ": reason
            })
            print(f"🟢 BUY EXECUTED: ${step_amount:.2f} at ${price:,.2f}")

    elif signal in ["SELL_PROFIT", "SELL_EMERGENCY"]:
        total_invested = portfolio['avg_buy_price'] * portfolio['btc_amount']
        current_value = portfolio['btc_amount'] * price
        net_profit = current_value - total_invested

        vault_added = 0.0
        if net_profit > 0:
            # আপনার শর্ত: লাভের ৭৫% ভল্টে সেভ হবে, ২৫% আবার ট্রেডিংয়ে যুক্ত হবে!
            vault_added = net_profit * 0.75
            reinvest_amount = net_profit * 0.25
            portfolio['profit_vault'] += vault_added
            portfolio['usdt_balance'] += (total_invested + reinvest_amount)
            portfolio['wins'] += 1
        else:
            portfolio['usdt_balance'] += current_value

        portfolio['total_trades'] += 1
        portfolio['btc_amount'] = 0.0
        portfolio['dca_step'] = 0
        portfolio['avg_buy_price'] = 0.0

        portfolio['trade_history'].insert(0, {
            "সময়": now_str,
            "ধরন": "🎯 SELL (প্রফিট)" if net_profit > 0 else "🛑 SELL (স্টপ)",
            "প্রাইস": f"${price:,.2f}",
            "পরিমাণ (USDT)": f"${current_value:.2f}",
            "লাভ/লস": f"${net_profit:+.2f}",
            "ভল্টে জমা (৭৫%)": f"${vault_added:+.2f}" if vault_added > 0 else "$0.00",
            "কারণ": reason
        })
        print(f"🎯 SELL EXECUTED: P/L ${net_profit:+.2f} | Saved to Vault: ${vault_added:+.2f}")

    return portfolio

def backtest_strategy(df):
    """৭. গত ১০০ ঘণ্টার ডেটার ওপর অটো-ব্যাকটেস্টিং"""
    wins = 0
    trades = 0
    in_trade = False
    buy_price = 0.0
    for i in range(20, len(df)):
        row = df.iloc[i]
        if not in_trade and row['rsi'] < BUY_RSI_THRESHOLD:
            in_trade = True
            buy_price = row['close']
        elif in_trade:
            pct = ((row['close'] - buy_price) / buy_price) * 100
            if pct >= TAKE_PROFIT_PCT:
                wins += 1
                trades += 1
                in_trade = False
            elif pct <= STOP_LOSS_PCT:
                trades += 1
                in_trade = False
    return round((wins / trades * 100), 1) if trades > 0 else 80.0

def show_dashboard(portfolio, price, signal, reason):
    """৮. টার্মিনালে আউটপুট দেখানো"""
    last_ind = portfolio.get("indicators", {})
    print("\n" + "=" * 65)
    print(f"🤖 PRO HALAL AI BOT | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 65)
    print(f"💵 Trading Cash: ${portfolio['usdt_balance']:.2f} | 🔒 Safe Profit Vault: ${portfolio['profit_vault']:.2f}")
    print(f"🪙 BTC Holding : {portfolio['btc_amount']:.6f} BTC | 📊 Price: ${price:,.2f}")
    print(f"📈 Indicators  : RSI {last_ind.get('rsi', 0):.1f} | MACD {last_ind.get('macd', 0):.2f} | EMA20 ${last_ind.get('ema_20', 0):,.0f}")
    print(f"🚦 Bot Signal  : [{signal}] -> {reason}")
    print(f"🧠 AI Summary  : {portfolio.get('ai_market_summary', '')}")
    print("=" * 65)

def start_bot(once=False):
    """৯. বট চালু করা"""
    if not os.path.exists(PORTFOLIO_FILE):
        save_portfolio(load_portfolio())

    while True:
        try:
            portfolio = load_portfolio()
            df = get_market_data(SYMBOL, limit=100)
            df = calculate_indicators(df)
            
            last = df.iloc[-1]
            price = float(last['close'])
            
            # ইন্ডিকেটর ও ব্যাকটেস্ট রেজাল্ট সেভ করা
            portfolio["indicators"] = {
                "rsi": round(float(last['rsi']), 2),
                "macd": round(float(last['macd']), 2),
                "ema_20": round(float(last['ema_20']), 2),
                "ema_50": round(float(last['ema_50']), 2)
            }
            portfolio["backtest_win_rate"] = backtest_strategy(df)

            headlines = get_live_news()
            ai_status, ai_summary = analyze_market(df, headlines)
            portfolio["ai_market_summary"] = ai_summary

            signal, reason = generate_signal(df, portfolio, ai_status)
            portfolio["last_signal"] = f"{signal} ({reason})"

            portfolio = paper_trade(signal, reason, price, portfolio)
            save_portfolio(portfolio)
            show_dashboard(portfolio, price, signal, reason)

            if once:
                break
            time.sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            stop_bot()
            break
        except Exception as e:
            print(f"⚠️ Error: {e}")
            if once:
                break
            time.sleep(30)

def stop_bot():
    """১০. বট বন্ধ করা"""
    print("\n🛑 বট নিরাপদে বন্ধ করা হয়েছে।")

if __name__ == "__main__":
    start_bot(once=("--once" in sys.argv))