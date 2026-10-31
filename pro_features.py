import time
from datetime import datetime

def analyze_pro_roadmap(df, portfolio, current_price):
    """
    ছবির Trading Roadmap অনুযায়ী ৪টি পিলার বিশ্লেষণ:
    1. Market Analysis (Structure, Key Levels, Price Action)
    2. Risk Management (Sizing, Exit, Capital Protection)
    3. Trading Psychology (Fear/Greed, Discipline, Patience)
    4. Trading Process (Strategy, Testing, Review)
    """
    last = df.iloc[-1]
    
    # ১. Market Analysis: Support, Resistance, Structure & Price Action
    support = float(df['low'].tail(30).min())
    resistance = float(df['high'].tail(30).max())
    
    ema_diff_pct = abs(last['ema_20'] - last['ema_50']) / current_price * 100
    if ema_diff_pct < 0.25:
        structure = "🔄 RANGE (সাইডওয়েজ মার্কেট)"
    elif last['ema_20'] > last['ema_50']:
        structure = "📈 UPTREND (বুলিশ স্ট্রাকচার)"
    else:
        structure = "📉 DOWNTREND (বিয়ারিশ স্ট্রাকচার)"

    # ক্যান্ডেলস্টিক প্রাইস অ্যাকশন (উইক রিজেকশন ও মোমেন্টাম)
    lower_wick = min(last['open'], last['close']) - last['low']
    upper_wick = last['high'] - max(last['open'], last['close'])
    body = abs(last['close'] - last['open'])
    
    if lower_wick > body * 1.5:
        price_action = "🟢 Bullish Rejection (নিচ থেকে ক্রেতাদের চাপ)"
    elif upper_wick > body * 1.5:
        price_action = "🔴 Bearish Rejection (উপর থেকে বিক্রেতাদের চাপ)"
    elif last['close'] > last['open']:
        price_action = "⚡ Bullish Momentum (সবুজ ক্যান্ডেল শক্তি)"
    else:
        price_action = "🔻 Bearish Momentum (লাল ক্যান্ডেল চাপ)"

    # ২. Trading Psychology & Discipline
    rsi = float(last['rsi'])
    trades_today = portfolio.get("trades_today", 0)
    daily_limit = portfolio.get("daily_trade_limit", 5)
    
    discipline_status = "✅ প্ল্যান অনুযায়ী চলছে (No Overtrading)" if trades_today < daily_limit else "🛑 আজকের লিমিট পূর্ণ (Overtrading Protected)"
    patience_status = "🧘 ধৈর্য ধরে সেরা সেটআপের অপেক্ষায়" if portfolio.get("btc_amount", 0) == 0 else "🎯 ট্রেড চালু আছে, টার্গেটের অপেক্ষায়"

    return {
        "market_structure": structure,
        "support_level": round(support, 2),
        "resistance_level": round(resistance, 2),
        "price_action": price_action,
        "discipline": discipline_status,
        "patience": patience_status,
        "emotion_state": "Fear (কেনার সুযোগ)" if rsi < 45 else ("Greed (সতর্ক থাকুন)" if rsi > 65 else "Balanced (স্বাভাবিক)")
    }

def update_periodic_report(portfolio, current_price, signal, reason, interval_hours=4):
    """
    প্রতি ৪ ঘণ্টা পর পর বটের কাজের বিস্তারিত বাংলা রিপোর্ট (Journal & Review) তৈরি করবে
    """
    if "periodic_reports" not in portfolio:
        portfolio["periodic_reports"] = []
    if "last_report_ts" not in portfolio:
        portfolio["last_report_ts"] = 0

    now_ts = time.time()
    hours_passed = (now_ts - portfolio["last_report_ts"]) / 3600.0

    # প্রথমবার রান হলে অথবা ৪ ঘণ্টা পার হলে অথবা নতুন Buy/Sell হলে রিপোর্ট লিখবে
    is_trade_action = signal in ["BUY", "SELL_PROFIT", "SELL_EMERGENCY"]
    if portfolio["last_report_ts"] == 0 or hours_passed >= interval_hours or is_trade_action:
        total_btc_val = portfolio.get('btc_amount', 0.0) * current_price
        grand_total = portfolio.get('usdt_balance', 100.0) + total_btc_val + portfolio.get('profit_vault', 0.0)
        net_pnl = grand_total - 100.0
        
        roadmap = portfolio.get("roadmap_data", {})
        
        if signal == "BUY":
            action_text = f"🟢 **নতুন ক্রয় (BUY):** বট `${current_price:,.2f}` দামে বিটকয়েন কিনেছে (DCA ধাপ {portfolio.get('dca_step', 1)}/3)।"
        elif signal in ["SELL_PROFIT", "SELL_EMERGENCY"]:
            action_text = f"🎯 **বিক্রয় সম্পন্ন (SELL):** বট `${current_price:,.2f}` দামে বিটকয়েন বিক্রি করেছে। কারণ: {reason}।"
        else:
            action_text = f"⏳ **অপেক্ষা (HOLD):** গত কয়েক ঘণ্টায় বট কোনো কয়েন কেনা-বেচা করেনি। কারণ: {reason}।"

        report_entry = {
            "সময়": datetime.now().strftime('%Y-%m-%d %I:%M %p'),
            "ধরন": "⚡ ট্রেড অ্যাকশন রিপোর্ট" if is_trade_action else "🕒 ৪-ঘণ্টার রুটিন চেকআপ রিপোর্ট",
            "বটের কাজ": action_text,
            "মার্কেট কন্ডিশন": f"স্ট্রাকচার: {roadmap.get('market_structure', 'N/A')} | সাপোর্ট: ${roadmap.get('support_level', 0):,.0f} | রেজিস্ট্যান্স: ${roadmap.get('resistance_level', 0):,.0f}",
            "লাভ/লস ও ভল্ট": f"মোট ব্যালেন্স: ${grand_total:.2f} (লাভ/লস: ${net_pnl:+.2f}) | 🔒 প্রফিট ভল্টে জমা: ${portfolio.get('profit_vault', 0.0):.2f}"
        }
        
        portfolio["periodic_reports"].insert(0, report_entry)
        portfolio["periodic_reports"] = portfolio["periodic_reports"][:15] # সর্বশেষ ১৫টি রিপোর্ট রাখবে
        portfolio["last_report_ts"] = now_ts

    return portfolio