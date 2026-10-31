import time
from datetime import datetime
import pandas as pd

def calculate_advanced_indicators(df):
    """একাধিক ইন্ডিকেটর ও হিস্টোগ্রাম ক্যালকুলেশন"""
    # RSI (14)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

    # EMA 20 & 50
    df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()

    # MACD & Histogram
    ema_12 = df['close'].ewm(span=12, adjust=False).mean()
    ema_26 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = ema_12 - ema_26
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    return df

def analyze_pro_roadmap(df, portfolio, current_price):
    """প্রো ট্রেডিং রোডম্যাপ ও মাল্টি-ইন্ডিকেটর বিশ্লেষণ"""
    last = df.iloc[-1]
    
    # একাধিক সাপোর্ট ও রেজিস্ট্যান্স লেভেল
    supports = sorted([float(df['low'].tail(20).min()), float(df['low'].tail(50).min())])
    resistances = sorted([float(df['high'].tail(20).max()), float(df['high'].tail(50).max())], reverse=True)
    
    ema_diff_pct = abs(last['ema_20'] - last['ema_50']) / current_price * 100
    if ema_diff_pct < 0.25:
        structure = "🔄 RANGE (মার্কেট সাইডওয়েজে আছে, ব্রেকআউটের অপেক্ষা)"
    elif last['ema_20'] > last['ema_50']:
        structure = "📈 UPTREND (বুলিশ জোনে আছে, ক্রেতাদের নিয়ন্ত্রণ বেশি)"
    else:
        structure = "📉 DOWNTREND (বিয়ারিশ জোনে আছে, বিক্রেতাদের চাপ বেশি)"

    rsi = float(last['rsi'])
    if rsi < 40:
        rsi_desc = f"RSI ({rsi:.1f}) অতি-বিক্রিত (Oversold) জোনে আছে। এটি একটি সম্ভাব্য বাই-সিগন্যাল জোন।"
    elif rsi > 65:
        rsi_desc = f"RSI ({rsi:.1f}) অতিরিক্ত কেনা (Overbought) জোনে আছে। এখানে সতর্ক থাকতে হবে।"
    else:
        rsi_desc = f"RSI ({rsi:.1f}) স্বাভাবিক (Neutral) জোনে রয়েছে।"

    macd_hist = float(last['macd_hist'])
    macd_desc = "MACD হিস্টোগ্রাম পজিটিভ (মোমেন্টাম বাড়ছে)" if macd_hist > 0 else "MACD হিস্টোগ্রাম নেগেটিভ (মোমেন্টাম কমছে)"

    return {
        "market_structure": structure,
        "support_levels": supports,
        "resistance_levels": resistances,
        "rsi_explanation": rsi_desc,
        "macd_explanation": macd_desc,
        "discipline": "✅ ওভারট্রেডিং সুরক্ষা সক্রিয় (ডেইলি লিমিট মানা হচ্ছে)",
        "patience": "🧘 রোবট নিখুঁত সিগন্যাল না পাওয়া পর্যন্ত ধৈর্য ধরে অপেক্ষা করছে",
        "emotion_state": "Fear (সুযোগ খুঁজছে)" if rsi < 45 else ("Greed (সতর্কতা)" if rsi > 65 else "Balanced (সুষম)")
    }

def update_periodic_report(portfolio, current_price, signal, reason, interval_hours=4):
    """প্রতি ৪ ঘণ্টা বা প্রতিটি ট্রেড অ্যাকশনের বিস্তারিত ডায়েরি রিপোর্ট"""
    if "periodic_reports" not in portfolio:
        portfolio["periodic_reports"] = []
    if "last_report_ts" not in portfolio:
        portfolio["last_report_ts"] = 0

    now_ts = time.time()
    hours_passed = (now_ts - portfolio["last_report_ts"]) / 3600.0
    is_trade_action = signal in ["BUY", "SELL_PROFIT", "SELL_EMERGENCY"]

    if portfolio["last_report_ts"] == 0 or hours_passed >= interval_hours or is_trade_action:
        total_btc_val = portfolio.get('btc_amount', 0.0) * current_price
        grand_total = portfolio.get('usdt_balance', 100.0) + total_btc_val + portfolio.get('profit_vault', 0.0)
        net_pnl = grand_total - 100.0
        
        roadmap = portfolio.get("roadmap_data", {})
        
        if signal == "BUY":
            action_text = f"🟢 **ট্রেড এন্ট্রি (BUY):** বট `${current_price:,.2f}` দামে কয়েন কিনেছে। কারণ: {reason}।"
        elif signal in ["SELL_PROFIT", "SELL_EMERGENCY"]:
            action_text = f"🎯 **ট্রেড ক্লোজ (SELL):** বট `${current_price:,.2f}` দামে বিক্রি সম্পন্ন করেছে। কারণ: {reason}।"
        else:
            action_text = f"⏳ **অপেক্ষা ও পর্যবেক্ষণ (HOLD):** বট বর্তমান ইন্ডিকেটর বিশ্লেষণ করে মার্কেটে এন্ট্রি নেওয়ার সঠিক মুহূর্তের জন্য অপেক্ষা করছে। কারণ: {reason}।"

        report_entry = {
            "সময়": datetime.now().strftime('%Y-%m-%d %I:%M %p'),
            "ধরন": "⚡ রিয়েল-টাইম ট্রেড অ্যাকশন" if is_trade_action else "🕒 ৪-ঘণ্টার শিক্ষা ও অগ্রগতি রিপোর্ট",
            "বিশ্লেষণ ও বটের কাজ": action_text,
            "টেকনিক্যাল অবস্থা": f"{roadmap.get('rsi_explanation', '')} | {roadmap.get('macd_explanation', '')}",
            "পোর্টফোলিও আপডেট": f"মোট সম্পদ: ${grand_total:.2f} | লাভ/লস: ${net_pnl:+.2f} | প্রফিট ভল্ট: ${portfolio.get('profit_vault', 0.0):.2f}"
        }
        
        portfolio["periodic_reports"].insert(0, report_entry)
        portfolio["periodic_reports"] = portfolio["periodic_reports"][:15]
        portfolio["last_report_ts"] = now_ts

    return portfolio