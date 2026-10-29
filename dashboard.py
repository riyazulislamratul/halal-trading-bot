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
    /* মেট্রিক কার্ডগুলোর মডার্ন ডিজাইন */
    div[data-testid="metric-container"] {
        background: linear-gradient(145deg, #161b22, #0d1117);
        border: 1px solid #30363d;
        padding: 16px;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.4);
    }
    /* ট্যাবগুলোর (Slots) মডার্ন বাটন ডিজাইন */
    button[data-baseweb="tab"] {
        font-size: 16px !important;
        font-weight: 600 !important;
        padding: 10px 20px !important;
        border-radius: 8px 8px 0px 0px !important;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# ২. সিক্রেট কি (API Key) এবং পিন লোড করা
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
# ৩. সিকিউরিটি লক স্ক্রিন (PIN Checkpoint)
# ==========================================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown("<br><br><h2 style='text-align: center;'>🔒 সিকিউরিটি চেকপয়েন্ট</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #8b949e;'>আপনার প্রাইভেট হালাল ট্রেডিং টার্মিনালে প্রবেশ করতে গোপন পিন দিন:</p>", unsafe_allow_html=True)
    
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
# ৪. ফাস্ট ডেটা ও চার্ট লোডিং ফাংশন (Cached)
# ==========================================
def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        try:
            with open(PORTFOLIO_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "usdt_balance": 100.0,
        "btc_amount": 0.0,
        "avg_buy_price": 0.0,
        "dca_step": 0,
        "total_trades": 0,
        "wins": 0,
        "trade_history": [],
        "last_update": "এখনো সিঙ্ক হয়নি"
    }

# ৬০ সেকেন্ডের ক্যাশ দেওয়া হয়েছে যেন চ্যাট করার সময় বারবার চার্ট লোড হয়ে দেরি না করে!
@st.cache_data(ttl=60)
def get_chart_data():
    url = "https://api.binance.us/api/v3/klines?symbol=BTCUSDT&interval=1h&limit=60"
    res = requests.get(url, timeout=10).json()
    data = [[int(k[0]), float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])] for k in res]
    df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['time'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

@st.cache_resource
def get_ai_client(api_key):
    return genai.Client(api_key=api_key)

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
# ৫. ড্যাশবোর্ড হেডার ও কুইক অ্যাকশন বার
# ==========================================
head_col1, head_col2, head_col3 = st.columns([7, 1.2, 1.2])
with head_col1:
    st.title("⚡ PRO HALAL AI TRADING TERMINAL")
    st.caption(f"⏱️ সর্বশেষ আপডেট: {portfolio.get('last_update', 'N/A')} | 🛡️ মোড: 100% Spot Halal (No Margin/Interest)")
with head_col2:
    if st.button("🔄 রিফ্রেশ", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
with head_col3:
    if st.button("🔒 লক করুন", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()

# মেইন পোর্টফোলিও কার্ডস (সবসময় ওপরে থাকবে)
total_btc_val = portfolio['btc_amount'] * current_price
total_equity = portfolio['usdt_balance'] + total_btc_val
profit_loss = total_equity - 100.0

col1, col2, col3, col4 = st.columns(4)
col1.metric("💼 মোট পোর্টফোলিও ভ্যালু", f"${total_equity:,.2f}", f"{profit_loss:+.2f} USDT")
col2.metric("💵 ক্যাশ ব্যালেন্স (USDT)", f"${portfolio['usdt_balance']:,.2f}", f"DCA ধাপ: {portfolio['dca_step']}/3")
col3.metric("🪙 বিটকয়েন হোল্ডিং (BTC)", f"{portfolio['btc_amount']:.6f} BTC", f"গড় কেনা দাম: ${portfolio['avg_buy_price']:,.2f}")
col4.metric("📊 বর্তমান BTC প্রাইস", f"${current_price:,.2f}", f"মোট ট্রেড: {portfolio['total_trades']} (জয়: {portfolio['wins']})")

st.write("") # সামান্য ফাঁকা জায়গা

# ==========================================
# ৬. আলাদা আলাদা স্লট / ট্যাব (Click to Switch)
# ==========================================
tab_chart, tab_ai, tab_history, tab_settings = st.tabs([
    "📊 ওভারভিউ ও লাইভ চার্ট", 
    "🤖 HalalCopilot (AI চ্যাট)", 
    "📜 ট্রেড হিস্ট্রি", 
    "⚙️ সিস্টেম ও স্ট্র্যাটেজি"
])

# ------------------------------------------
# স্লট ১: লাইভ মার্কেট চার্ট এবং মার্কেট সামারি
# ------------------------------------------
with tab_chart:
    st.subheader("🕯️ BTC/USDT লাইভ ক্যান্ডেলস্টিক চার্ট (1H)")
    fig = go.Figure(data=[go.Candlestick(
        x=df_chart['time'],
        open=df_chart['open'],
        high=df_chart['high'],
        low=df_chart['low'],
        close=df_chart['close'],
        increasing_line_color='#00ff88',
        decreasing_line_color='#ff3366'
    )])
    fig.update_layout(
        template="plotly_dark", 
        height=460, 
        margin=dict(l=10, r=10, t=10, b=10), 
        xaxis_rangeslider_visible=False,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(22,27,34,0.6)'
    )
    st.plotly_chart(fig, use_container_width=True)

    # চার্টের নিচে ৬০ ঘণ্টার হাই-লো সামারি
    c1, c2, c3 = st.columns(3)
    c1.info(f"📈 **গত ৬০ ঘণ্টার সর্বোচ্চ দাম:** ${df_chart['high'].max():,.2f}")
    c2.warning(f"📉 **গত ৬০ ঘণ্টার সর্বনিম্ন দাম:** ${df_chart['low'].min():,.2f}")
    price_change = current_price - df_chart['open'].iloc[0]
    c3.success(f"⚡ **৬০ ঘণ্টায় প্রাইস পরিবর্তন:** ${price_change:+,.2f}")

# ------------------------------------------
# স্লট ২: HalalCopilot (সুপার-ফাস্ট AI চ্যাট ও ভয়েস)
# ------------------------------------------
with tab_ai:
    st.subheader("🤖 HalalCopilot সহকারী (সুপার-ফাস্ট মোড)")
    st.caption("আপনার পোর্টফোলিও এবং লাইভ মার্কেট সম্পর্কে যেকোনো প্রশ্ন করুন অথবা এক ক্লিকে কুইক বাটন চাপুন:")

    # চ্যাট হিস্ট্রি জমানোর মেমোরি
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # কুইক অ্যাকশন বাটন (টাইপ না করে এক ক্লিকে প্রশ্ন করার জন্য)
    q_col1, q_col2, q_col3 = st.columns(3)
    quick_prompt = None
    if q_col1.button("📊 এখন মার্কেটের অবস্থা কেমন?", use_container_width=True):
        quick_prompt = "এখন বিটকয়েনের মার্কেট প্রাইস ও চার্টের অবস্থা কেমন? সংক্ষেপে বলো।"
    if q_col2.button("💼 আমার পোর্টফোলিও বিশ্লেষণ করো", use_container_width=True):
        quick_prompt = "আমার বর্তমান ব্যালেন্স, বিটকয়েন হোল্ডিং এবং লাভ-ক্ষতির অবস্থা বিশ্লেষণ করে বলো।"
    if q_col3.button("💡 এখন কি কেনা উচিত?", use_container_width=True):
        quick_prompt = "আমার গড় কেনা দাম এবং বর্তমান বিটকয়েন প্রাইস অনুযায়ী এখন কি নতুন করে কেনা ঠিক হবে নাকি অপেক্ষা করব?"

    st.divider()

    # ম্যানুয়াল ইনপুট এবং মাইক্রোফোন কমান্ড
    input_col1, input_col2 = st.columns([3, 1])
    with input_col1:
        user_query = st.text_input("আপনার প্রশ্ন লিখুন:", placeholder="যেমন: আমার কত লাভ বা লস চলছে?")
    with input_col2:
        st.write("ভয়েস কমান্ড:")
        audio_data = mic_recorder(start_prompt="🎙️ কথা বলুন", stop_prompt="⏹️ থামুন", key='mic')

    ask_btn = st.button("জিজ্ঞেস করুন 🚀", type="primary", use_container_width=True)

    # কোন প্রশ্নটি যাবে তা নির্ধারণ করা
    final_query = None
    if quick_prompt:
        final_query = quick_prompt
    elif audio_data:
        st.toast("🎙️ ভয়েস কমান্ড গ্রহণ করা হয়েছে!")
        final_query = "মার্কেটের বর্তমান অবস্থা এবং আমার পোর্টফোলিও বিশ্লেষণ করে সংক্ষেপে বলুন।"
    elif ask_btn:
        final_query = user_query if user_query else "মার্কেট এবং আমার পোর্টফোলিওর কী অবস্থা বলো।"

    if final_query:
        with st.spinner("⚡ HalalCopilot উত্তর তৈরি করছে..."):
            try:
                ai_client = get_ai_client(GEMINI_API_KEY)
                
                prompt_text = f"""
                বর্তমান BTC প্রাইস: ${current_price:,.2f}
                ইউজারের পোর্টফোলিও: মোট ইক্যুইটি ${total_equity:,.2f}, ক্যাশ ${portfolio['usdt_balance']:,.2f}, BTC {portfolio['btc_amount']:.6f}, গড় কেনা দাম ${portfolio['avg_buy_price']:,.2f}, DCA ধাপ {portfolio['dca_step']}/3।
                ইউজারের প্রশ্ন: {final_query}
                """
                
                # আপডেট করা Gemini 3.8 Flash ও Interactions API (অফিসিয়াল রিকোয়ারমেন্ট)
                interaction = ai_client.interactions.create(
                    model='models/gemini-3.8-flash',
                    input=prompt_text,
                    system_instruction="তুমি HalalCopilot, একজন বন্ধুসুলভ ও প্রফেশনাল ট্রেডিং সহকারী। ইউজারের সাথে বাংলায় খুব সাবলীল ও স্বাভাবিক মানুষের মতো কথা বলবে। উত্তর সবসময় সংক্ষেপে (২ থেকে ৪ লাইনের মধ্যে) এবং টু-দ্য-পয়েন্টে দেবে যাতে দ্রুত পড়া ও শোনা যায়।",
                    generation_config={
                        'max_output_tokens': 300,
                        'temperature': 0.7,
                    }
                )
                
                answer = interaction.steps[-1]
                
                # চ্যাট হিস্ট্রিতে সেভ করা
                st.session_state.chat_history.insert(0, {"q": final_query, "a": answer})
                speak_text(answer)
                
            except Exception as e:
                st.error(f"কানেকশন সমস্যা: {e}")

    # চ্যাট হিস্ট্রি স্ক্রিনে দেখানো
    if st.session_state.chat_history:
        st.markdown("#### 💬 কথোপকথন:")
        for chat in st.session_state.chat_history[:5]: # সর্বশেষ ৫টি মেসেজ দেখাবে
            with st.chat_message("user"):
                st.write(chat["q"])
            with st.chat_message("assistant"):
                st.write(chat["a"])

# ------------------------------------------
# স্লট ৩: বটের বাই-সেল রেকর্ড (Trade History)
# ------------------------------------------
with tab_history:
    st.subheader("📜 বটের বাই-সেল রেকর্ড ও পারফরম্যান্স")
    
    win_rate = (portfolio['wins'] / portfolio['total_trades'] * 100) if portfolio['total_trades'] > 0 else 0.0
    h_col1, h_col2, h_col3 = st.columns(3)
    h_col1.metric("🎯 উইন রেট (Win Rate)", f"{win_rate:.1f}%")
    h_col2.metric("🔄 মোট সম্পন্ন ট্রেড", f"{portfolio['total_trades']} টি")
    h_col3.metric("✅ সফল প্রফিট ট্রেড", f"{portfolio['wins']} টি")
    
    st.divider()
    
    if portfolio.get("trade_history"):
        df_history = pd.DataFrame(portfolio["trade_history"])
        st.dataframe(df_history, use_container_width=True)
    else:
        st.info("🕒 বট এখনো কোনো কয়েন কেনা-বেচা করেনি। মার্কেটে সঠিক সিগন্যাল (Smart DCA + Candlestick Pattern) পেলেই এখানে অটোমেটিক রেকর্ড চলে আসবে।")

# ------------------------------------------
# স্লট ৪: সিস্টেম স্ট্যাটাস ও হালাল স্ট্র্যাটেজি ইনফো
# ------------------------------------------
with tab_settings:
    st.subheader("⚙️ সিস্টেম ডায়াগনস্টিক ও স্ট্র্যাটেজি কনফিগারেশন")
    
    s_col1, s_col2 = st.columns(2)
    with s_col1:
        st.markdown("#### 🔌 কানেকশন স্ট্যাটাস")
        if GEMINI_API_KEY and GEMINI_API_KEY.startswith("AIza"):
            st.success(f"✅ **Gemini API সচল আছে** (Key: `{GEMINI_API_KEY[:6]}...`)")
        elif GEMINI_API_KEY:
            st.warning(f"⚠️ **API Key ফরম্যাট সন্দেহজনক** (Key: `{GEMINI_API_KEY[:6]}...` - এটি AIza দিয়ে শুরু হওয়া উচিত)")
        else:
            st.error("❌ **কোনো API Key পাওয়া যায়নি!**")
            
        st.info("📡 **মার্কেট ডেটা সোর্স:** Binance US Spot API (1H Candlesticks)")
        st.info(f"📁 **পোর্টফোলিও ফাইল:** `{PORTFOLIO_FILE}`")

    with s_col2:
        st.markdown("#### 🛡️ হালাল ট্রেডিং শর্তাবলি ও স্ট্র্যাটেজি")
        st.markdown("""
        * **১০০% স্পট ট্রেডিং:** কোনো প্রকার লিভারেজ, মার্জিন বা সুদ (Riba) নেই।
        * **স্মার্ট DCA (৩ ধাপ):** মার্কেট নিচে নামলে একসাথে সব টাকা না ঢেলে ৩ ধাপে গড় করে কেনা হয়।
        * **ক্যান্ডেলস্টিক ও লিকুইডিটি সুইপ:** ৭টি প্রাইস অ্যাকশন প্যাটার্ন এবং ভলিউম কনফার্মেশন ছাড়া বট এন্ট্রি নেয় না।
        """)