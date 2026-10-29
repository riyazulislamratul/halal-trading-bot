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
# ১. পেজ কনফিগারেশন এবং ক্লিন UI (বিগিনার ফ্রেন্ডলি)
# ==========================================
st.set_page_config(page_title="Halal AI Bot & Mentor", layout="wide", page_icon="🤖")

st.markdown("""
<style>
    div[data-testid="metric-container"] {
        background: linear-gradient(145deg, #161b22, #0d1117);
        border-left: 4px solid #3399ff;
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 4px 15px rgba(51, 153, 255, 0.1);
    }
    .bot-title { font-size: 24px; font-weight: bold; color: #3399ff; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# ২. সিক্রেট কি এবং পিন লোড করা
# ==========================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or (st.secrets["GEMINI_API_KEY"] if "GEMINI_API_KEY" in st.secrets else None)
DASHBOARD_PIN = os.getenv("DASHBOARD_PIN") or (st.secrets["DASHBOARD_PIN"] if "DASHBOARD_PIN" in st.secrets else "6251")
PORTFOLIO_FILE = "paper_portfolio.json"

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown("<br><br><h2 style='text-align: center; color: #3399ff;'>🔒 বট কন্ট্রোল প্যানেল</h2>", unsafe_allow_html=True)
    col_a, col_b, col_c = st.columns([1, 1.2, 1])
    with col_b:
        entered_pin = st.text_input("বট মাস্টার পিন (PIN):", type="password", placeholder="পিন দিন...")
        if st.button("ড্যাশবোর্ড আনলক করুন 🔓", use_container_width=True):
            if entered_pin == str(DASHBOARD_PIN).strip():
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("❌ ভুল পিন! আবার চেষ্টা করুন।")
    st.stop()

# ==========================================
# ৩. ফাস্ট ডেটা লোডিং এবং ক্যাশ
# ==========================================
def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        try:
            with open(PORTFOLIO_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "usdt_balance": 100.0, "btc_amount": 0.0, "avg_buy_price": 0.0,
        "dca_step": 0, "total_trades": 0, "wins": 0, "trade_history": []
    }

@st.cache_data(ttl=60)
def get_chart_data():
    url = "https://api.binance.us/api/v3/klines?symbol=BTCUSDT&interval=1h&limit=60"
    res = requests.get(url, timeout=10).json()
    data = [[int(k[0]), float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])] for k in res]
    df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['time'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

df_chart = get_chart_data()
current_price = df_chart['close'].iloc[-1]
portfolio = load_portfolio()

# ==========================================
# ৪. হেডার ও অটো-ট্রেড মেট্রিক্স
# ==========================================
st.markdown('<p class="bot-title">🤖 হালাল অটো-ট্রেডিং বট এবং মেন্টর</p>', unsafe_allow_html=True)
st.caption("বট নিজেই মার্কেট অ্যানালাইসিস করে ট্রেড করবে, আপনি শুধু ড্যাশবোর্ড থেকে মনিটর করবেন এবং শিখবেন।")

total_btc_val = portfolio['btc_amount'] * current_price
total_equity = portfolio['usdt_balance'] + total_btc_val
profit_loss = total_equity - 100.0

col1, col2, col3, col4 = st.columns(4)
col1.metric("💼 মোট ব্যালেন্স", f"${total_equity:,.2f}", f"প্রফিট: {profit_loss:+.2f} USDT")
col2.metric("💵 ক্যাশ (USDT)", f"${portfolio['usdt_balance']:,.2f}", f"DCA ধাপ: {portfolio['dca_step']}/3")
col3.metric("🪙 বটের BTC হোল্ডিং", f"{portfolio['btc_amount']:.5f} BTC", f"গড় কেনা: ${portfolio['avg_buy_price']:,.2f}")
col4.metric("📊 লাইভ মার্কেট", f"${current_price:,.2f}", "অটো-ট্রেড অ্যাক্টিভ 🟢")

st.write("")

# ==========================================
# ৫. ড্যাশবোর্ড ট্যাব (Learning Focus)
# ==========================================
tab_ai, tab_chart, tab_history = st.tabs(["🎓 HalalCopilot (বটের থেকে শিখুন)", "📈 বটের লাইভ মার্কেট ভিউ", "📜 বটের অ্যাকশন হিস্ট্রি"])

# --- ট্যাব ১: এআই মেন্টর (Learning Hub) ---
with tab_ai:
    st.subheader("🎓 HalalCopilot - আপনার ট্রেডিং মেন্টর")
    st.caption("বটের বর্তমান অ্যাকশন বা মার্কেটের অবস্থা নিয়ে যেকোনো প্রশ্ন করুন। এআই আপনাকে সহজ ভাষায় শিখিয়ে দেবে।")
    
    q_col1, q_col2, q_col3 = st.columns(3)
    quick_query = None
    if q_col1.button("🤔 মার্কেট এখন আপ নাকি ডাউন?", use_container_width=True):
        quick_query = "মার্কেট এখন কোন দিকে যাচ্ছে? সহজ করে বুঝিয়ে বলো যাতে আমি ট্রেডিং শিখতে পারি।"
    if q_col2.button("💡 বট এখন কী করবে?", use_container_width=True):
        quick_query = "আমার পোর্টফোলিও এবং বর্তমান প্রাইস দেখে বলো, বট কি এখন বাই করবে নাকি ওয়েট করবে? কেন করবে তার লজিক বোঝাও।"
    if q_col3.button("📊 DCA স্ট্র্যাটেজি কী?", use_container_width=True):
        quick_query = "আমার বট যে DCA স্ট্র্যাটেজি ব্যবহার করে, সেটি আসলে কী? আমি কীভাবে এটি থেকে লাভ করব সহজ বাংলায় বোঝাও।"

    user_query = st.text_input("আপনি নিজে থেকে কিছু শিখতে চাইলে এখানে লিখুন:")
    final_query = quick_query if quick_query else user_query

    if st.button("বটকে জিজ্ঞেস করুন 🚀") or final_query:
        if final_query:
            with st.spinner("HalalCopilot আপনার জন্য উত্তর তৈরি করছে..."):
                try:
                    ai_client = genai.Client(api_key=GEMINI_API_KEY)
                    prompt_text = f"""
                    লাইভ BTC প্রাইস: ${current_price:,.2f}
                    বটের পোর্টফোলিও: টোটাল ${total_equity:,.2f}, ক্যাশ ${portfolio['usdt_balance']:,.2f}, BTC {portfolio['btc_amount']}
                    ইউজারের প্রশ্ন: {final_query}
                    """
                    interaction = ai_client.interactions.create(
                        model='models/gemini-3.8-flash',
                        input=prompt_text,
                        system_instruction="তুমি HalalCopilot, একজন ফ্রেন্ডলি 'ট্রেডিং টিচার' বা মেন্টর। ইউজার ট্রেডিং শিখতে চায় এবং বট দিয়ে অটো-ট্রেড করায়। তুমি ইউজারকে খুব সহজ বাংলায় (২-৪ লাইনে) মার্কেটের অবস্থা এবং বটের লজিক বুঝিয়ে দেবে। কোনো কঠিন কথা বলবে না, একদম বিগিনারদের মতো করে শেখাবে।",
                    )
                    st.success(interaction.steps[-1])
                except Exception as e:
                    st.error(f"এপিআই সমস্যা: {e}")

# --- ট্যাব ২: ক্লিন মার্কেট ভিউ ---
with tab_chart:
    st.subheader("📈 বট যে চার্ট দেখে অ্যানালাইজ করছে (১ ঘণ্টার টাইমফ্রেম)")
    fig = go.Figure(data=[go.Candlestick(
        x=df_chart['time'], open=df_chart['open'], high=df_chart['high'],
        low=df_chart['low'], close=df_chart['close'],
        increasing_line_color='#00ff88', decreasing_line_color='#ff3366'
    )])
    fig.update_layout(template="plotly_dark", height=450, xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

# --- ট্যাব ৩: বটের অ্যাকশন হিস্ট্রি ---
with tab_history:
    st.subheader("📜 বট কবে কী কিনেছে বা বেচেছে")
    if portfolio.get("trade_history"):
        st.dataframe(pd.DataFrame(portfolio["trade_history"]), use_container_width=True)
    else:
        st.info("🕒 বট এখনো কোনো ট্রেড নেয়নি। মার্কেটে সঠিক লজিক ম্যাচ করলেই এখানে অটোমেটিক রেকর্ড চলে আসবে এবং আপনি দেখে শিখতে পারবেন।")