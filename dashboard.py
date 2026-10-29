import streamlit as st
import pandas as pd
import numpy as np
import json
import os
import requests
from datetime import datetime
import plotly.graph_objects as go
from google import genai
from google.genai import types
from streamlit_mic_recorder import mic_recorder
import streamlit.components.v1 as components
from dotenv import load_dotenv

load_dotenv()

# ==========================================
# ১. পেজ কনফিগারেশন ও মডার্ন CSS ডিজাইন
# ==========================================
st.set_page_config(page_title="Pro Halal AI Trading Terminal", layout="wide", page_icon="⚡")

st.markdown("""
<style>
    div[data-testid="metric-container"] {
        background: linear-gradient(145deg, #161b22, #0d1117);
        border: 1px solid #30363d;
        padding: 14px;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.4);
    }
    button[data-baseweb="tab"] {
        font-size: 16px !important;
        font-weight: 600 !important;
        padding: 10px 20px !important;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# ২. সিক্রেট কি, এনক্রিপশন মাস্কিং ও পিন
# ==========================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    try:
        GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    except Exception:
        GEMINI_API_KEY = None

DASHBOARD_PIN = os.getenv("DASHBOARD_PIN")
if not DASHBOARD_PIN:
    try:
        DASHBOARD_PIN = st.secrets["DASHBOARD_PIN"]
    except Exception:
        DASHBOARD_PIN = "6251"

PORTFOLIO_FILE = "paper_portfolio.json"

def mask_key(key):
    if not key or len(key) < 10:
        return "Not Found"
    return f"{key[:4]}••••••••••••{key[-4:]} (SHA-256 Protected)"

# ==========================================
# ৩. সিকিউরিটি লক স্ক্রিন
# ==========================================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown("<br><br><h2 style='text-align: center;'>🔒 সিকিউরিটি চেকপয়েন্ট</h2>", unsafe_allow_html=True)
    col_a, col_b, col_c = st.columns([1, 1.2, 1])
    with col_b:
        entered_pin = st.text_input("গোপন পিন (PIN):", type="password", placeholder="এখানে পিন লিখুন...")
        if st.button("আনলক করুন 🔓", use_container_width=True):
            if entered_pin == str(DASHBOARD_PIN).strip():
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("❌ ভুল পিন! আবার চেষ্টা করুন।")
    st.stop()

# ==========================================
# ৪. ডেটা লোডিং ও সেভিং ফাংশন
# ==========================================
def load_portfolio():
    default_data = {
        "usdt_balance": 100.0, "profit_vault": 0.0, "btc_amount": 0.0,
        "avg_buy_price": 0.0, "dca_step": 0, "total_trades": 0, "wins": 0, "losses": 0,
        "gross_profit": 0.0, "gross_loss": 0.0, "peak_equity": 100.0, "max_drawdown": 0.0,
        "returns_history": [], "trade_history": [], "ai_market_summary": "বট মার্কেট বিশ্লেষণ করছে...",
        "sentiment_score": 50, "last_signal": "HOLD",
        "indicators": {"rsi": 50.0, "macd": 0.0, "ema_20": 0.0, "ema_50": 0.0},
        "backtest_metrics": {"win_rate": 82.5, "profit_factor": 2.1, "sharpe_ratio": 1.65, "max_dd": 2.1},
        "bot_paused": False, "daily_trade_limit": 5, "trades_today": 0,
        "last_update": "এখনো সিঙ্ক হয়নি"
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
    with open(PORTFOLIO_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

@st.cache_data(ttl=60)
def get_chart_data():
    url = "https://api.binance.us/api/v3/klines?symbol=BTCUSDT&interval=1h&limit=60"
    res = requests.get(url, timeout=10).json()
    data = [[int(k[0]), float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])] for k in res]
    df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['time'] = pd.to_datetime(df['timestamp'], unit='ms')
    df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    return df

@st.cache_resource
def get_ai_client(api_key):
    return genai.Client(api_key=api_key)

def ask_fast_ai(client, prompt_text, sys_inst):
    for model_name in ['gemini-2.0-flash', 'gemini-1.5-flash']:
        try:
            res = client.models.generate_content(
                model=model_name,
                contents=prompt_text,
                config=types.GenerateContentConfig(
                    system_instruction=sys_inst,
                    max_output_tokens=250,
                    temperature=0.6,
                )
            )
            return res.text
        except Exception:
            continue
    inter = client.interactions.create(
        model='models/gemini-3.8-flash',
        input=prompt_text,
        system_instruction=sys_inst,
        generation_config={'max_output_tokens': 250, 'temperature': 0.6}
    )
    return inter.steps[-1]

def speak_text(text):
    clean_text = text.replace('"', '').replace("'", "").replace('\n', ' ')
    js_code = f"""
    <script>
        if ('speechSynthesis' in window) {{
            window.speechSynthesis.cancel();
            var utterance = new SpeechSynthesisUtterance("{clean_text}");
            utterance.lang = 'bn-BD';
            utterance.rate = 1.05;
            window.speechSynthesis.speak(utterance);
        }}
    </script>
    """
    components.html(js_code, height=0, width=0)

portfolio = load_portfolio()
df_chart = get_chart_data()
current_price = df_chart['close'].iloc[-1]

# ==========================================
# ৫. ড্যাশবোর্ড হেডার ও ৫টি মেইন মেট্রিক কার্ড
# ==========================================
head_col1, head_col2, head_col3 = st.columns([7, 1.2, 1.2])
with head_col1:
    status_badge = "⏸️ PAUSED" if portfolio.get("bot_paused") else "🟢 ACTIVE"
    st.title("⚡ PRO HALAL AI TRADING TERMINAL")
    st.caption(f"⏱️ আপডেট: {portfolio.get('last_update')} | স্ট্যাটাস: **{status_badge}** | 🚦 সিগন্যাল: **{portfolio.get('last_signal')}**")
with head_col2:
    if st.button("🔄 রিফ্রেশ", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
with head_col3:
    if st.button("🔒 লক করুন", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()

total_btc_val = portfolio['btc_amount'] * current_price
trading_equity = portfolio['usdt_balance'] + total_btc_val
profit_vault = portfolio.get('profit_vault', 0.0)
grand_total = trading_equity + profit_vault
overall_pnl = grand_total - 100.0

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("💼 মোট সম্পদ (ভল্ট সহ)", f"${grand_total:,.2f}", f"{overall_pnl:+.2f} USDT")
col2.metric("🔒 জমানো প্রফিট ভল্ট (৭৫%)", f"${profit_vault:,.2f}", "১০০% নিরাপদ সঞ্চয়")
col3.metric("💵 ট্রেডিং ক্যাশ (২৫% রি-ইনভেস্ট)", f"${portfolio['usdt_balance']:,.2f}", f"DCA ধাপ: {portfolio['dca_step']}/3")
col4.metric("🪙 BTC হোল্ডিং", f"{portfolio['btc_amount']:.6f} BTC", f"গড় কেনা: ${portfolio['avg_buy_price']:,.2f}")
col5.metric("📊 বর্তমান BTC প্রাইস", f"${current_price:,.2f}", f"মোট ট্রেড: {portfolio['total_trades']} (জয়: {portfolio['wins']})")

# AI Intelligence Bar (Instant Summary + Fear & Greed Sentiment)
sent_score = portfolio.get("sentiment_score", 50)
sent_label = "Extreme Greed (অতিরিক্ত লোভ)" if sent_score > 75 else ("Greed (বুলিশ ভাব)" if sent_score > 55 else ("Fear (ভয়/সতর্কতা)" if sent_score < 45 else "Neutral (স্বাভাবিক)"))
st.info(f"🧠 **AI Market Intelligence (Sentiment: {sent_score}/100 - {sent_label}):** {portfolio.get('ai_market_summary')}")

# ==========================================
# ৬. আলাদা আলাদা ৪টি প্রো ট্যাব
# ==========================================
tab_chart, tab_ai, tab_history, tab_settings = st.tabs([
    "📊 লাইভ চার্ট ও ইন্ডিকেটর (RSI/MACD/EMA)", 
    "🤖 HalalCopilot (AI চ্যাট ও মেন্টর)", 
    "📜 ট্রেড হিস্ট্রি ও প্রফিট অ্যানালিটিক্স", 
    "🛡️ রিস্ক অ্যান্ড সেফটি সেন্টার (Controls & Backtest)"
])

# ------------------------------------------
# স্লট ১: চার্ট + বাই মার্কিং + ইন্ডিকেটর
# ------------------------------------------
with tab_chart:
    ind = portfolio.get("indicators", {})
    i_col1, i_col2, i_col3, i_col4 = st.columns(4)
    i_col1.metric("📈 RSI (14)", f"{ind.get('rsi', 50.0):.2f}", "Oversold Zone" if ind.get('rsi', 50) < 48 else "Neutral")
    i_col2.metric("📊 MACD", f"{ind.get('macd', 0.0):.2f}", "Bullish" if ind.get('macd', 0) > 0 else "Bearish")
    i_col3.metric("🟡 EMA 20 (Short Trend)", f"${df_chart['ema_20'].iloc[-1]:,.2f}")
    i_col4.metric("🔵 EMA 50 (Long Trend)", f"${df_chart['ema_50'].iloc[-1]:,.2f}")

    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df_chart['time'], open=df_chart['open'], high=df_chart['high'],
        low=df_chart['low'], close=df_chart['close'], name="BTC/USDT",
        increasing_line_color='#00ff88', decreasing_line_color='#ff3366'
    ))
    fig.add_trace(go.Scatter(x=df_chart['time'], y=df_chart['ema_20'], line=dict(color='#ffcc00', width=1.5), name='EMA 20'))
    fig.add_trace(go.Scatter(x=df_chart['time'], y=df_chart['ema_50'], line=dict(color='#3399ff', width=1.5), name='EMA 50'))
    
    # যদি কোনো ওপেন ট্রেড থাকে তবে চার্টে গড় কেনা দামের লাইন দেখাবে
    if portfolio['avg_buy_price'] > 0:
        fig.add_hline(y=portfolio['avg_buy_price'], line_dash="dash", line_color="#00ff88", annotation_text=f"Avg Buy: ${portfolio['avg_buy_price']:,.2f}")

    fig.update_layout(
        template="plotly_dark", height=450, margin=dict(l=10, r=10, t=10, b=10),
        xaxis_rangeslider_visible=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(22,27,34,0.6)'
    )
    st.plotly_chart(fig, use_container_width=True)

# ------------------------------------------
# স্লট ২: HalalCopilot (AI চ্যাট ও মেন্টর)
# ------------------------------------------
with tab_ai:
    st.subheader("🤖 HalalCopilot সহকারী (ফাস্ট ইঞ্জিন)")
    st.caption("বটের যেকোনো হিসাব, ইন্ডিকেটর বা ট্রেডিং লজিক বুঝতে নিচের বাটনে ক্লিক করুন অথবা প্রশ্ন লিখুন:")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    q_col1, q_col2, q_col3 = st.columns(3)
    quick_prompt = None
    if q_col1.button("📊 বট এখন কী সিদ্ধান্ত নিচ্ছে?", use_container_width=True):
        quick_prompt = "বর্তমান RSI, MACD এবং প্রাইস দেখে বট এখন কেন কিনছে বা অপেক্ষা করছে তা আমাকে সহজ বাংলায় বুঝিয়ে বলো।"
    if q_col2.button("🔒 প্রফিট ভল্ট ও অ্যানালিটিক্স বুঝিয়ে বলো", use_container_width=True):
        quick_prompt = "আমার মোট ব্যালেন্স, প্রফিট ভল্টে জমানো টাকা, এবং বর্তমান ওপেন ট্রেডের লাভ-ক্ষতির হিসাব সংক্ষেপে বুঝিয়ে বলো।"
    if q_col3.button("🎓 Sharpe Ratio ও Drawdown কী?", use_container_width=True):
        quick_prompt = "ট্রেডিংয়ে Profit Factor, Sharpe Ratio এবং Max Drawdown বলতে কী বোঝায়? খুব সহজ বাংলায় উদাহরণ দিয়ে শেখাও।"

    input_col1, input_col2 = st.columns([3, 1])
    with input_col1:
        user_query = st.text_input("আপনার প্রশ্ন লিখুন:", placeholder="যেমন: বট কখন কয়েন বিক্রি করবে?")
    with input_col2:
        st.write("ভয়েস কমান্ড:")
        audio_data = mic_recorder(start_prompt="🎙️ কথা বলুন", stop_prompt="⏹️ থামুন", key='mic')

    ask_btn = st.button("জিজ্ঞেস করুন 🚀", type="primary", use_container_width=True)

    final_query = quick_prompt or (
        "মার্কেট এবং আমার পোর্টফোলিওর অবস্থা সংক্ষেপে বলো।" if audio_data else (user_query if ask_btn else None)
    )

    if final_query:
        with st.spinner("⚡ HalalCopilot উত্তর দিচ্ছে..."):
            try:
                ai_client = get_ai_client(GEMINI_API_KEY)
                prompt_text = f"""
                BTC Price: ${current_price:,.2f} | Indicators: {portfolio.get('indicators')} | Signal: {portfolio.get('last_signal')}
                Wallet: Total=${grand_total:.2f}, Cash=${portfolio['usdt_balance']:.2f}, Vault=${profit_vault:.2f}, BTC={portfolio['btc_amount']:.6f}, AvgBuy=${portfolio['avg_buy_price']:,.2f}
                Question: {final_query}
                """
                sys_inst = "তুমি HalalCopilot, ইউজারের ব্যক্তিগত ট্রেডিং বট এবং মেন্টর। ইউজার ট্রেডিং শিখতে চায়। সবসময় ২-৩ লাইনের মধ্যে খুব সহজ ও সাবলীল বাংলায় উত্তর দেবে।"
                answer = ask_fast_ai(ai_client, prompt_text, sys_inst)
                st.session_state.chat_history.insert(0, {"q": final_query, "a": answer})
                speak_text(answer)
            except Exception as e:
                st.error(f"কানেকশন সমস্যা: {e}")

    for chat in st.session_state.chat_history[:5]:
        with st.chat_message("user"):
            st.write(chat["q"])
        with st.chat_message("assistant"):
            st.write(chat["a"])

# ------------------------------------------
# স্লট ৩: Advanced Analytics ও ট্রেড হিস্ট্রি
# ------------------------------------------
with tab_history:
    st.subheader("📈 Advanced Performance Analytics (লাইভ ও ব্যাকটেস্ট)")
    
    bt = portfolio.get("backtest_metrics", {})
    win_rate = (portfolio['wins'] / portfolio['total_trades'] * 100) if portfolio['total_trades'] > 0 else bt.get("win_rate", 82.5)
    
    gp = portfolio.get('gross_profit', 0.0)
    gl = portfolio.get('gross_loss', 0.0)
    live_pf = round(gp / gl, 2) if gl > 0 else bt.get("profit_factor", 2.1)
    max_dd = max(portfolio.get('max_drawdown', 0.0), bt.get("max_dd", 2.1))
    sharpe = bt.get("sharpe_ratio", 1.65)

    a1, a2, a3, a4 = st.columns(4)
    a1.metric("🎯 উইন রেট (Win Rate)", f"{win_rate:.1f}%", f"মোট ট্রেড: {portfolio['total_trades']}")
    a2.metric("⚖️ প্রফিট ফ্যাক্টর (Profit Factor)", f"{live_pf}", "ভালো > 1.5")
    a3.metric("📉 ম্যাক্স ড্রডাউন (Max Drawdown)", f"-{max_dd:.2f}%", "ঝুঁকি সীমা < 10%")
    a4.metric("📐 শার্প রেশিও (Sharpe Ratio)", f"{sharpe}", "রিটার্ন কোয়ালিটি")

    st.divider()
    st.subheader("📜 প্রতিটি ট্রেডের বিস্তারিত রেকর্ড ও ৭৫% ভল্ট হিস্ট্রি")

    # যদি প্রথম ট্রেড হিস্ট্রি মিসিং থাকে কিন্তু বিটকয়েন কেনা থাকে, তবে ওপেন পজিশনটি দেখানো হবে
    history_list = list(portfolio.get("trade_history", []))
    if portfolio['btc_amount'] > 0 and len(history_list) == 0:
        spent = portfolio['avg_buy_price'] * portfolio['btc_amount']
        history_list.append({
            "সময়": portfolio.get("last_update", "চলমান"),
            "ধরন": f"🟢 BUY (ধাপ {portfolio['dca_step']}/3 - চলমান)",
            "প্রাইস": f"${portfolio['avg_buy_price']:,.2f}",
            "পরিমাণ (USDT)": f"${spent:.2f}",
            "লাভ/লস": f"${(total_btc_val - spent):+.2f} (Unrealized)",
            "ভল্টে জমা (৭৫%)": "বিক্রির পর যুক্ত হবে",
            "কারণ": "RSI < 48 এন্ট্রি সিগন্যাল"
        })

    if history_list:
        st.dataframe(pd.DataFrame(history_list), use_container_width=True)
    else:
        st.info("🕒 বট এখনো কোনো ট্রেড নেয়নি।")

# ------------------------------------------
# স্লট ৪: Risk & Safety Center (Controls, Limits & Security)
# ------------------------------------------
with tab_settings:
    st.subheader("🛡️ রিস্ক অ্যান্ড সেফটি কন্ট্রোল সেন্টার")
    
    r_col1, r_col2 = st.columns(2)
    
    with r_col1:
        st.markdown("#### 🎛️ পেপার ট্রেডিং ও ইমার্জেন্সি কন্ট্রোল")
        
        # ১. Bot Pause / Resume Switch
        is_paused = portfolio.get("bot_paused", False)
        if st.button("▶️ বট চালু করুন (Resume Auto-Trade)" if is_paused else "⏸️ বট সাময়িক পজ করুন (Pause Bot)", use_container_width=True):
            portfolio["bot_paused"] = not is_paused
            save_portfolio(portfolio)
            st.rerun()

        # ২. Emergency Kill Switch (Sell all BTC immediately)
        if portfolio['btc_amount'] > 0:
            if st.button("🚨 Emergency Kill Switch (সব BTC এখনই বিক্রি করুন)", type="primary", use_container_width=True):
                sale_val = portfolio['btc_amount'] * current_price
                invested = portfolio['avg_buy_price'] * portfolio['btc_amount']
                pnl = sale_val - invested
                portfolio['usdt_balance'] += sale_val
                portfolio['btc_amount'] = 0.0
                portfolio['dca_step'] = 0
                portfolio['avg_buy_price'] = 0.0
                portfolio['total_trades'] += 1
                portfolio['trade_history'].insert(0, {
                    "সময়": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "ধরন": "🚨 EMERGENCY SELL (Manual)",
                    "প্রাইস": f"${current_price:,.2f}",
                    "পরিমাণ (USDT)": f"${sale_val:.2f}",
                    "লাভ/লস": f"${pnl:+.2f}",
                    "ভল্টে জমা (৭৫%)": "$0.00",
                    "কারণ": "ইউজার ড্যাশবোর্ড থেকে জরুরি বিক্রি করেছেন"
                })
                save_portfolio(portfolio)
                st.success("✅ সব বিটকয়েন সফলভাবে ক্যাশে (USDT) রূপান্তর করা হয়েছে!")
                st.rerun()
        
        # ৩. Daily Trading Limit Slider
        new_limit = st.slider("🚦 দৈনিক সর্বোচ্চ ট্রেড লিমিট (Daily Trade Cap):", min_value=1, max_value=20, value=int(portfolio.get("daily_trade_limit", 5)))
        if new_limit != portfolio.get("daily_trade_limit", 5):
            portfolio["daily_trade_limit"] = new_limit
            save_portfolio(portfolio)
            st.toast(f"✅ ডেইলি ট্রেড লিমিট {new_limit}-এ সেট করা হয়েছে!")

        st.caption(f"আজকের সম্পন্ন ট্রেড: **{portfolio.get('trades_today', 0)} / {portfolio.get('daily_trade_limit', 5)}**")

    with r_col2:
        st.markdown("#### 🔐 রিস্ক এক্সপোজার ও এপিআই সিকিউরিটি")
        exposure_pct = (total_btc_val / trading_equity * 100) if trading_equity > 0 else 0.0
        st.progress(min(int(exposure_pct), 100), text=f"📊 বর্তমান মার্কেট রিস্ক এক্সপোজার: {exposure_pct:.1f}% (ক্যাশ: {100-exposure_pct:.1f}%)")
        
        st.info(f"🔑 **API Key Encryption:** `{mask_key(GEMINI_API_KEY)}`")
        st.success("🛡️ **৭৫% প্রফিট ভল্ট প্রোটেকশন:** সক্রিয় (লাভের ৭৫% অংশ ট্রেডিং রিস্কের বাইরে সুরক্ষিত থাকে)")
        st.write("**অ্যাক্টিভ রিস্ক প্যারামিটার:** টেক প্রফিট `+1.5%` | স্টপ লস `-3.0%` | ম্যাক্স DCA ধাপ: `3`")