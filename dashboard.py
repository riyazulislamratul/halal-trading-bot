import streamlit as st
import pandas as pd
import json
import os
import requests
import plotly.graph_objects as go
from google import genai
from streamlit_mic_recorder import mic_recorder
import streamlit.components.v1 as components
from dotenv import load_dotenv

load_dotenv()

# ১. Streamlit পেজ কনফিগারেশন সবসময় সবার ওপরে থাকতে হয়
st.set_page_config(page_title="Pro Halal AI Trading Terminal", layout="wide", page_icon="🔒")

# ২. আগে লোকাল .env থেকে খুঁজবে, না পেলে Streamlit Cloud-এর Secrets থেকে নেবে
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
        DASHBOARD_PIN = "6251"  # ডিফল্ট পিন যদি কোথাও না পায়

PORTFOLIO_FILE = "paper_portfolio.json"

st.set_page_config(page_title="Pro Halal AI Trading Terminal", layout="wide", page_icon="🔒")

# পাসওয়ার্ড চেক করার সিস্টেম
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown("<h2 style='text-align: center;'>🔒 সিকিউরিটি চেকপয়েন্ট</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>আপনার প্রাইভেট হালাল ট্রেডিং টার্মিনালে প্রবেশ করতে গোপন পিন দিন:</p>", unsafe_allow_html=True)
    
    col_a, col_b, col_c = st.columns([1, 1.5, 1])
    with col_b:
        entered_pin = st.text_input("গোপন পিন (PIN):", type="password", placeholder="এখানে পিন লিখুন...")
        if st.button("আনলক করুন 🔓", use_container_width=True):
            if entered_pin == DASHBOARD_PIN:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("❌ ভুল পিন! আবার চেষ্টা করুন।")
    st.stop() # পিন না মিললে নিচের আর কোনো কোড রান হবে না!

# ==========================================
# ১. ডেটা লোড করার ফাংশন (লগইন সফল হলে নিচের অংশ কাজ করবে)
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

def get_chart_data():
    url = "https://api.binance.us/api/v3/klines?symbol=BTCUSDT&interval=1h&limit=60"
    res = requests.get(url, timeout=10).json()
    data = [[int(k[0]), float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])] for k in res]
    df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['time'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

portfolio = load_portfolio()
df_chart = get_chart_data()
current_price = df_chart['close'].iloc[-1]

# ==========================================
# ২. ব্রাউজারে ভয়েস আউটপুট (TTS) ফাংশন
# ==========================================
def speak_text(text):
    clean_text = text.replace('"', '').replace("'", "").replace('\n', ' ')
    js_code = f"""
    <script>
        if ('speechSynthesis' in window) {{
            window.speechSynthesis.cancel();
            var utterance = new SpeechSynthesisUtterance("{clean_text}");
            utterance.lang = 'bn-BD';
            utterance.rate = 1.0;
            window.speechSynthesis.speak(utterance);
        }}
    </script>
    """
    components.html(js_code, height=0, width=0)

# ==========================================
# ৩. ড্যাশবোর্ড হেডার ও লগআউট বাটন
# ==========================================
head_col1, head_col2 = st.columns([8, 1])
with head_col1:
    st.title("⚡ PRO HALAL AI TRADING TERMINAL")
    st.caption(f"সর্বশেষ আপডেট: {portfolio.get('last_update', 'N/A')} | স্ট্র্যাটেজি: Smart DCA + 7 Candlestick Patterns + Liquidity Sweep")
with head_col2:
    if st.button("লক করুন 🔒"):
        st.session_state.authenticated = False
        st.rerun()

total_btc_val = portfolio['btc_amount'] * current_price
total_equity = portfolio['usdt_balance'] + total_btc_val
profit_loss = total_equity - 100.0

col1, col2, col3, col4 = st.columns(4)
col1.metric("💼 মোট পোর্টফোলিও ভ্যালু", f"${total_equity:,.2f}", f"{profit_loss:+.2f} USDT")
col2.metric("💵 ক্যাশ ব্যালেন্স (USDT)", f"${portfolio['usdt_balance']:,.2f}", f"DCA ধাপ: {portfolio['dca_step']}/3")
col3.metric("🪙 বিটকয়েন হোল্ডিং (BTC)", f"{portfolio['btc_amount']:.6f} BTC", f"গড় কেনা দাম: ${portfolio['avg_buy_price']:,.2f}")
col4.metric("📊 বর্তমান BTC প্রাইস", f"${current_price:,.2f}", f"মোট ট্রেড: {portfolio['total_trades']} (জয়: {portfolio['wins']})")

st.divider()

# ==========================================
# ৪. লাইভ ক্যান্ডেলস্টিক চার্ট এবং HalalCopilot
# ==========================================
left_col, right_col = st.columns([2.2, 1])

with left_col:
    st.subheader("🕯️ লাইভ মার্কেট চার্ট (BTC/USDT - 1H)")
    fig = go.Figure(data=[go.Candlestick(
        x=df_chart['time'],
        open=df_chart['open'],
        high=df_chart['high'],
        low=df_chart['low'],
        close=df_chart['close'],
        increasing_line_color='#00ff88',
        decreasing_line_color='#ff3366'
    )])
    fig.update_layout(template="plotly_dark", height=450, margin=dict(l=10, r=10, t=10, b=10), xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("📜 বটের বাই-সেল রেকর্ড (Trade History)")
    if portfolio.get("trade_history"):
        st.dataframe(pd.DataFrame(portfolio["trade_history"]), use_container_width=True)
    else:
        st.info("বট এখনো কোনো কয়েন কেনা-বেচা করেনি। সঠিক সিগন্যাল পেলেই এখানে রেকর্ড চলে আসবে।")

with right_col:
    st.subheader("🤖 HalalCopilot সহকারী")
    st.caption("টাইপ করুন অথবা মাইক্রোফোনে কথা বলুন:")
    
    user_query = st.text_input("প্রশ্ন লিখুন...", placeholder="যেমন: এখন মার্কেটের অবস্থা কেমন?")
    
    st.write("অথবা ভয়েস কমান্ড দিন:")
    audio_data = mic_recorder(start_prompt="🎙️ কথা বলুন", stop_prompt="⏹️ থামুন", key='mic')
    
    final_query = user_query
    if audio_data:
        st.success("ভয়েস রেকর্ড সফল হয়েছে!")
        final_query = "মার্কেটের বর্তমান অবস্থা এবং আমার পোর্টফোলিও বিশ্লেষণ করে বলুন।"

    if st.button("জিজ্ঞেস করুন 🚀") or audio_data:
        query_to_send = final_query if final_query else "মার্কেটের কী অবস্থা বলো"
        if query_to_send:
            with st.spinner("HalalCopilot তোমার সাথে কথা বলছে..."):
                try:
                    ai_client = genai.Client(api_key=GEMINI_API_KEY)
                    
                    prompt_text = f"""
                    বর্তমান মার্কেট প্রাইস: ${current_price}
                    ইউজারের ওয়ালেট ডেটা: {json.dumps(portfolio)}
                    ইউজারের প্রশ্ন বা কথা: {query_to_send}
                    
                    নির্দেশনা: তুমি একজন পেশাদার রিয়েল এমপ্লয়ি এবং ট্রেডিং সহকারী (HalalCopilot)। ইউজারের সাথে সরাসরি একজন মানুষ বা অভিজ্ঞ কলিগ যেভাবে কথা বলে, সেভাবে বাংলায় খোলামেলা ও বন্ধুসুলভভাবে কথা বলবে। কোনো রোবটিক বা কঠিন ফরম্যাট ব্যবহার করবে না। একদম সরাসরি উত্তর দেবে।
                    """
                    
                    interaction = ai_client.interactions.create(
                        model='models/gemini-3.8-flash',
                        input=prompt_text,
                        system_instruction='তুমি HalalCopilot, কোম্পানির একজন বিশ্বস্ত ও প্রফেশনাল ট্রেডিং অ্যাসিস্ট্যান্ট বা এমপ্লয়ি। ইউজারের সাথে সরাসরি একজন মানুষের মতো বাংলায় স্বাভাবিক ও সাবলীলভাবে কথা বলবে। রোবটের মতো কৃত্রিম বা কঠিন ভাষা ব্যবহার করবে না।',
                        generation_config={
                            'max_output_tokens': 600,
                            'thinking_level': 'low',
                        },
                    )
                    
                    answer = interaction.steps[-1]
                    st.success(answer)
                    speak_text(answer)
                    
                except Exception as e:
                    st.error(f"কানেকশন সমস্যা: {e}")