import streamlit as st
import pandas as pd
import json
import os
import requests
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
# ২. সিক্রেট কি এবং পিন লোড করা
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
# ৪. ডেটা, ইন্ডিকেটর ও ফাস্ট AI ফাংশন
# ==========================================
def load_portfolio():
    default_data = {
        "usdt_balance": 100.0, "profit_vault": 0.0, "btc_amount": 0.0,
        "avg_buy_price": 0.0, "dca_step": 0, "total_trades": 0, "wins": 0,
        "trade_history": [], "ai_market_summary": "বট মার্কেট বিশ্লেষণ করছে...",
        "last_signal": "HOLD", "indicators": {"rsi": 50.0, "macd": 0.0, "ema_20": 0.0, "ema_50": 0.0},
        "backtest_win_rate": 80.0, "last_update": "এখনো সিঙ্ক হয়নি"
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

@st.cache_data(ttl=60)
def get_chart_data():
    url = "https://api.binance.us/api/v3/klines?symbol=BTCUSDT&interval=1h&limit=60"
    res = requests.get(url, timeout=10).json()
    data = [[int(k[0]), float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])] for k in res]
    df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['time'] = pd.to_datetime(df['timestamp'], unit='ms')
    # চার্টে দেখানোর জন্য EMA 20 ও EMA 50
    df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    return df

@st.cache_resource
def get_ai_client(api_key):
    return genai.Client(api_key=api_key)

def ask_fast_ai(client, prompt_text, sys_inst):
    """প্রথমে সুপার-ফাস্ট স্ট্যান্ডার্ড মডেল চেষ্টা করবে, না পেলে 3.8-flash ফলব্যাক করবে"""
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
    # Fallback to Interactions API
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
# ৫. ড্যাশবোর্ড হেডার ও ৫টি মেইন মেট্রিক কার্ড (প্রফিট ভল্ট সহ)
# ==========================================
head_col1, head_col2, head_col3 = st.columns([7, 1.2, 1.2])
with head_col1:
    st.title("⚡ PRO HALAL AI TRADING TERMINAL")
    st.caption(f"⏱️ সর্বশেষ সিঙ্ক: {portfolio.get('last_update')} | 🚦 সর্বশেষ বট সিগন্যাল: **{portfolio.get('last_signal')}**")
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

# বটের রেডিমেড ইনস্ট্যান্ট এআই রিপোর্ট (০ সেকেন্ডে লোড হবে!)
st.info(f"🧠 **বটের তাৎক্ষণিক এআই মার্কেট রিপোর্ট:** {portfolio.get('ai_market_summary', 'বিশ্লেষণ চলছে...')}")

# ==========================================
# ৬. আলাদা আলাদা ৪টি ট্যাব
# ==========================================
tab_chart, tab_ai, tab_history, tab_settings = st.tabs([
    "📊 লাইভ চার্ট ও ইন্ডিকেটর (RSI/MACD/EMA)", 
    "🤖 HalalCopilot (AI চ্যাট ও মেন্টর)", 
    "📜 ট্রেড হিস্ট্রি ও ভল্ট রেকর্ড", 
    "⚙️ ব্যাকটেস্টিং ও সিস্টেম স্ট্যাটাস"
])

# ------------------------------------------
# স্লট ১: চার্ট + RSI, MACD, EMA
# ------------------------------------------
with tab_chart:
    ind = portfolio.get("indicators", {})
    i_col1, i_col2, i_col3, i_col4 = st.columns(4)
    i_col1.metric("📈 RSI (14)", f"{ind.get('rsi', 50.0):.2f}", "Oversold < 48" if ind.get('rsi', 50) < 48 else "Neutral/High")
    i_col2.metric("📊 MACD", f"{ind.get('macd', 0.0):.2f}", "Bullish" if ind.get('macd', 0) > 0 else "Bearish")
    i_col3.metric("🟡 EMA 20 (Short)", f"${df_chart['ema_20'].iloc[-1]:,.2f}")
    i_col4.metric("🔵 EMA 50 (Long)", f"${df_chart['ema_50'].iloc[-1]:,.2f}")

    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df_chart['time'], open=df_chart['open'], high=df_chart['high'],
        low=df_chart['low'], close=df_chart['close'], name="BTC/USDT",
        increasing_line_color='#00ff88', decreasing_line_color='#ff3366'
    ))
    fig.add_trace(go.Scatter(x=df_chart['time'], y=df_chart['ema_20'], line=dict(color='#ffcc00', width=1.5), name='EMA 20'))
    fig.add_trace(go.Scatter(x=df_chart['time'], y=df_chart['ema_50'], line=dict(color='#3399ff', width=1.5), name='EMA 50'))
    fig.update_layout(
        template="plotly_dark", height=450, margin=dict(l=10, r=10, t=10, b=10),
        xaxis_rangeslider_visible=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(22,27,34,0.6)'
    )
    st.plotly_chart(fig, use_container_width=True)

# ------------------------------------------
# স্লট ২: HalalCopilot (সুপার ফাস্ট AI)
# ------------------------------------------
with tab_ai:
    st.subheader("🤖 HalalCopilot সহকারী (ফাস্ট ইঞ্জিন)")
    st.caption("বটের যেকোনো হিসাব বা ট্রেডিং লজিক বুঝতে নিচের বাটনে ক্লিক করুন অথবা প্রশ্ন লিখুন:")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    q_col1, q_col2, q_col3 = st.columns(3)
    quick_prompt = None
    if q_col1.button("📊 বট এখন কী সিদ্ধান্ত নিচ্ছে?", use_container_width=True):
        quick_prompt = "বর্তমান RSI, MACD এবং প্রাইস দেখে বট এখন কেন কিনছে বা অপেক্ষা করছে তা আমাকে সহজ বাংলায় বুঝিয়ে বলো।"
    if q_col2.button("🔒 প্রফিট ভল্ট ও লাভ-লসের হিসাব দাও", use_container_width=True):
        quick_prompt = "আমার মোট ব্যালেন্স, প্রফিট ভল্টে জমানো টাকা এবং বর্তমান লাভ-ক্ষতির হিসাব সংক্ষেপে বুঝিয়ে বলো।"
    if q_col3.button("🎓 RSI ও EMA দেখে কীভাবে শিখব?", use_container_width=True):
        quick_prompt = "চার্টের বর্তমান RSI এবং EMA 20/50 এর মান দেখে মার্কেট কোন দিকে যাচ্ছে তা একজন নতুন শিক্ষার্থীকে যেভাবে শেখায় সেভাবে বলো।"

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
                BTC Price: ${current_price:,.2f} | Indicators: {portfolio.get('indicators')} | Last Bot Signal: {portfolio.get('last_signal')}
                Wallet: Total=${grand_total:.2f}, Trading Cash=${portfolio['usdt_balance']:.2f}, Safe Profit Vault (75% saved)=${profit_vault:.2f}, BTC={portfolio['btc_amount']:.6f}
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
# স্লট ৩: ট্রেড হিস্ট্রি ও ভল্ট রেকর্ড
# ------------------------------------------
with tab_history:
    st.subheader("📜 বটের কেনা-বেচা এবং ৭৫% প্রফিট ভল্টের রেকর্ড")
    if portfolio.get("trade_history"):
        st.dataframe(pd.DataFrame(portfolio["trade_history"]), use_container_width=True)
    else:
        st.info("🕒 বট এখনো প্রথম ট্রেড নেয়নি। নিচে দেওয়া কমান্ড দিয়ে বটটি একবার রান করলেই সিগন্যাল অনুযায়ী কেনা-বেচা শুরু হয়ে যাবে!")

# ------------------------------------------
# স্লট ৪: ব্যাকটেস্টিং ও সিস্টেম স্ট্যাটাস
# ------------------------------------------
with tab_settings:
    st.subheader("⚙️ অটো-ব্যাকটেস্টিং ও প্রফিট ভল্ট রুলস")
    b_col1, b_col2 = st.columns(2)
    with b_col1:
        st.metric("🧪 ব্যাকটেস্ট উইন রেট (গত ১০০ ঘণ্টা)", f"{portfolio.get('backtest_win_rate', 80.0)}%", "স্ট্র্যাটেজি: RSI + MACD + EMA")
        st.success("✅ **৭৫% প্রফিট ভল্ট রুল সচল আছে:** বট প্রতিবার লাভ করার পর ৭৫% টাকা আলাদা করে প্রফিট ভল্টে লক করে ফেলবে এবং মাত্র ২৫% লাভ মূল টাকার সাথে রি-ইনভেস্ট করবে।")
    with b_col2:
        st.markdown("#### 🔧 বটের সবকটি অ্যাক্টিভ মডিউল:")
        st.code("""
✔ get_market_data()      -> Live Price & OHLCV
✔ calculate_indicators() -> RSI (14), MACD, EMA (20/50)
✔ analyze_market()       -> Pre-computed AI Bangla Summary
✔ generate_signal()      -> Buy / Sell / Hold Logic
✔ calculate_risk()       -> Dynamic DCA Step Sizing
✔ paper_trade()          -> 75% Profit Vault + 25% Re-invest
✔ backtest_strategy()    -> 100-Hour Historical Simulation
        """)