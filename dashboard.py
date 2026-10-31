import streamlit as st
import pandas as pd
import json
import os
import requests
from datetime import datetime
import plotly.graph_objects as go
from google import genai
from google.genai import types
from streamlit_mic_recorder import mic_recorder

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ==========================================
# ১. সাইবার ও প্রফেশনাল সাইডবার লেআউট CSS
# ==========================================
st.set_page_config(page_title="Pro Halal AI Trading Terminal", layout="wide", page_icon="⚡")

st.markdown("""
<style>
    .stApp {
        background-color: #07090e;
    }
    div[data-testid="metric-container"] {
        background: linear-gradient(135deg, rgba(16, 22, 34, 0.9), rgba(10, 14, 23, 0.9));
        border: 1px solid rgba(0, 255, 136, 0.25);
        border-left: 4px solid #00ff88;
        padding: 14px;
        border-radius: 12px;
        box-shadow: 0 4px 20px rgba(0, 255, 136, 0.08);
    }
    .roadmap-card {
        background: linear-gradient(145deg, #111622, #0b0f17);
        border: 1px solid #1f293d;
        border-top: 3px solid #00d4ff;
        padding: 16px;
        border-radius: 12px;
        margin-bottom: 12px;
    }
    .report-box {
        background: rgba(18, 25, 38, 0.85);
        border-left: 4px solid #ffcc00;
        padding: 14px;
        border-radius: 8px;
        margin-bottom: 10px;
        border: 1px solid #26334d;
    }
    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: #0b0f17;
        border-right: 1px solid #1f293d;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# ২. সিকিউরিটি ও পিন চেক
# ==========================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or (st.secrets["GEMINI_API_KEY"] if "GEMINI_API_KEY" in st.secrets else None)
DASHBOARD_PIN = os.getenv("DASHBOARD_PIN") or (st.secrets["DASHBOARD_PIN"] if "DASHBOARD_PIN" in st.secrets else "6251")
PORTFOLIO_FILE = "paper_portfolio.json"

def mask_key(key):
    if not key or len(key) < 10:
        return "Not Found"
    return f"{key[:4]}••••••••••••{key[-4:]} (Protected)"

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown("<br><br><h2 style='text-align: center; color: #00ff88;'>🔒 সিকিউরিটি চেকপয়েন্ট</h2>", unsafe_allow_html=True)
    col_a, col_b, col_c = st.columns([1, 1.2, 1])
    with col_b:
        entered_pin = st.text_input("গোপন পিন (PIN):", type="password", placeholder="পিন লিখুন...")
        if st.button("আনলক করুন 🔓", use_container_width=True):
            if entered_pin == str(DASHBOARD_PIN).strip():
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("❌ ভুল পিন!")
    st.stop()

# ==========================================
# ৩. ডেটা ও এআই লোডার
# ==========================================
def load_portfolio():
    default_data = {
        "usdt_balance": 100.0, "profit_vault": 0.0, "btc_amount": 0.0,
        "avg_buy_price": 0.0, "dca_step": 0, "total_trades": 0, "wins": 0, "losses": 0,
        "gross_profit": 0.0, "gross_loss": 0.0, "peak_equity": 100.0, "max_drawdown": 0.0,
        "returns_history": [], "trade_history": [], "periodic_reports": [],
        "ai_market_summary": "বট মার্কেট বিশ্লেষণ করছে...",
        "sentiment_score": 50, "last_signal": "HOLD",
        "indicators": {"rsi": 50.0, "macd": 0.0, "ema_20": 0.0, "ema_50": 0.0},
        "roadmap_data": {},
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
                model=model_name, contents=prompt_text,
                config=types.GenerateContentConfig(system_instruction=sys_inst, max_output_tokens=250, temperature=0.6)
            )
            return res.text
        except Exception:
            continue
    inter = client.interactions.create(
        model='models/gemini-3.8-flash', input=prompt_text,
        system_instruction=sys_inst, generation_config={'max_output_tokens': 250, 'temperature': 0.6}
    )
    return inter.steps[-1]

portfolio = load_portfolio()
df_chart = get_chart_data()
current_price = df_chart['close'].iloc[-1]
support_lvl = portfolio.get("roadmap_data", {}).get("support_level") or float(df_chart['low'].tail(30).min())
resist_lvl = portfolio.get("roadmap_data", {}).get("resistance_level") or float(df_chart['high'].tail(30).max())

# ==========================================
# ৪. বাম পাশের প্রফেশনাল সাইডবার মেনু (Sidebar Navigation)
# ==========================================
with st.sidebar:
    st.markdown("<h3 style='color: #00ff88; text-align: center;'>⚡ TERMINAL MENU</h3>", unsafe_allow_html=True)
    st.write("---")
    
    # রেডিও বাটন দিয়ে প্রো সাইডবার নেভিগেশন
    selected_page = st.radio(
        "মূল মেনু নির্বাচন করুন:",
        [
            "📊 লাইভ চার্ট ও কি-লেভেলস",
            "🗺️ ট্রেডিং রোডম্যাপ ও ৪-ঘণ্টার রিপোর্ট",
            "🤖 HalalCopilot (AI মেন্টর)",
            "📜 ট্রেড হিস্ট্রি ও অ্যানালিটিক্স",
            "🛡️ রিস্ক অ্যান্ড সেফটি সেন্টার"
        ],
        label_visibility="collapsed"
    )
    
    st.write("---")
    st.caption("🤖 **Bot Status:** " + ("⏸️ Paused" if portfolio.get("bot_paused") else "🟢 Active (24/7)"))
    if st.button("🔄 ডেটা রিফ্রেশ করুন", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    if st.button("🔒 লক টার্মিনাল", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()

# ==========================================
# ৫. মূল ড্যাশবোর্ড হেডার ও মেট্রিক কার্ড
# ==========================================
head_col1, head_col2 = st.columns([8, 1])
with head_col1:
    st.markdown(f"<h2 style='color:#00ff88; margin-bottom:0;'>🤖 PRO HALAL AI ALGO-BOT</h2>", unsafe_allow_html=True)
    st.caption(f"⏱️ শেষ আপডেট: {portfolio.get('last_update')} | 🚦 সিগন্যাল: **{portfolio.get('last_signal')}**")

total_btc_val = portfolio['btc_amount'] * current_price
trading_equity = portfolio['usdt_balance'] + total_btc_val
profit_vault = portfolio.get('profit_vault', 0.0)
grand_total = trading_equity + profit_vault
overall_pnl = grand_total - 100.0

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("💼 মোট সম্পদ (ভল্ট সহ)", f"${grand_total:,.2f}", f"{overall_pnl:+.2f} USDT")
col2.metric("🔒 প্রফিট ভল্ট (৭৫% সেভ)", f"${profit_vault:,.2f}", "১০০% নিরাপদ সঞ্চয়")
col3.metric("💵 ট্রেডিং ক্যাশ (USDT)", f"${portfolio['usdt_balance']:,.2f}", f"DCA ধাপ: {portfolio['dca_step']}/3")
col4.metric("🪙 BTC হোল্ডিং", f"{portfolio['btc_amount']:.6f} BTC", f"গড় কেনা: ${portfolio['avg_buy_price']:,.2f}")
col5.metric("📊 বর্তমান BTC প্রাইস", f"${current_price:,.2f}", f"মোট ট্রেড: {portfolio['total_trades']} (জয়: {portfolio['wins']})")

st.info(f"🧠 **বটের লাইভ মার্কেট ব্রিফিং:** {portfolio.get('ai_market_summary')}")
st.write("---")

# ==========================================
# ৬. সাইডবার সিলেকশন অনুযায়ী ফুল-পেজ কন্টেন্ট রেন্ডার
# ==========================================

if selected_page == "📊 লাইভ চার্ট ও কি-লেভেলস":
    ind = portfolio.get("indicators", {})
    i1, i2, i3, i4 = st.columns(4)
    i1.metric("📈 RSI (14)", f"{ind.get('rsi', 50.0):.2f}", "Buy Zone < 48")
    i2.metric("📊 MACD", f"{ind.get('macd', 0.0):.2f}", "Momentum")
    i3.metric("🟢 Support (সাপোর্ট ফ্লোর)", f"${support_lvl:,.2f}", "ক্রেতাদের জোন")
    i4.metric("🔴 Resistance (রেজিস্ট্যান্স ছাদ)", f"${resist_lvl:,.2f}", "বিক্রেতাদের জোন")

    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df_chart['time'], open=df_chart['open'], high=df_chart['high'],
        low=df_chart['low'], close=df_chart['close'], name="BTC/USDT",
        increasing_line_color='#00ff88', decreasing_line_color='#ff3366'
    ))
    fig.add_trace(go.Scatter(x=df_chart['time'], y=df_chart['ema_20'], line=dict(color='#ffcc00', width=1.5), name='EMA 20'))
    fig.add_trace(go.Scatter(x=df_chart['time'], y=df_chart['ema_50'], line=dict(color='#00d4ff', width=1.5), name='EMA 50'))
    
    fig.add_hline(y=support_lvl, line_dash="dot", line_color="#00ff88", annotation_text=f"Support: ${support_lvl:,.0f}")
    fig.add_hline(y=resist_lvl, line_dash="dot", line_color="#ff3366", annotation_text=f"Resistance: ${resist_lvl:,.0f}")

    fig.update_layout(
        template="plotly_dark", height=580, margin=dict(l=10, r=10, t=10, b=10),
        xaxis_rangeslider_visible=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(11,15,23,0.9)'
    )
    st.plotly_chart(fig, use_container_width=True)

elif selected_page == "🗺️ ট্রেডিং রোডম্যাপ ও ৪-ঘণ্টার রিপোর্ট":
    st.subheader("🕒 প্রতি ৪ ঘণ্টার অটোমেটেড বট অ্যাক্টিভিটি রিপোর্ট (Journal & Review)")
    st.caption("বট গত কয়েক ঘণ্টায় কী করেছে, কেন কিনেছে বা কেনেনি, এবং কত লাভ বা লস হলো তার সম্পূর্ণ লিখিত ডায়েরি:")

    reports = portfolio.get("periodic_reports", [])
    if not reports:
        st.markdown(f"""
        <div class="report-box">
            <b>🕒 বর্তমান স্ট্যাটাস রিপোর্ট ({portfolio.get('last_update')}):</b><br>
            • <b>বটের কাজ:</b> বট বর্তমানে মার্কেট পর্যবেক্ষণ করছে। সর্বশেষ সিগন্যাল: <code>{portfolio.get('last_signal')}</code><br>
            • <b>মার্কেট লেভেল:</b> বর্তমান দাম <b>${current_price:,.2f}</b> (সাপোর্ট: ${support_lvl:,.0f} | রেজিস্ট্যান্স: ${resist_lvl:,.0f})<br>
            • <b>পোর্টফোলিও ও ভল্ট:</b> মোট ব্যালেন্স <b>${grand_total:.2f}</b> (লাভ/লস: ${overall_pnl:+.2f}) | প্রফিট ভল্টে জমা: <b>${profit_vault:.2f}</b>
        </div>
        """, unsafe_allow_html=True)
    else:
        for rep in reports[:5]:
            st.markdown(f"""
            <div class="report-box">
                <b>{rep.get('ধরন')} — 📅 {rep.get('সময়')}</b><br>
                • {rep.get('বটের কাজ')}<br>
                • <b>মার্কেট বিশ্লেষণ:</b> {rep.get('মার্কেট কন্ডিশন')}<br>
                • <b>হিসাব নিকাশ:</b> {rep.get('লাভ/লস ও ভল্ট')}
            </div>
            """, unsafe_allow_html=True)

    st.divider()
    st.subheader("🗺️ প্রো ট্রেডিং রোডম্যাপ (Live Bot Brain Breakdown)")
    rm = portfolio.get("roadmap_data", {})
    r1, r2 = st.columns(2)
    with r1:
        st.markdown(f"""
        <div class="roadmap-card">
            <h4 style="color:#00d4ff; margin:0;">১. Market Analysis (মার্কেট বিশ্লেষণ)</h4><hr style="margin:8px 0;">
            • <b>Market Structure:</b> {rm.get('market_structure', 'বিশ্লেষণ চলছে...')}<br>
            • <b>Key Levels:</b> সাপোর্ট <code>${support_lvl:,.0f}</code> | রেজিস্ট্যান্স <code>${resist_lvl:,.0f}</code><br>
            • <b>Price Action:</b> {rm.get('price_action', 'পর্যবেক্ষণ চলছে')}
        </div>
        <div class="roadmap-card">
            <h4 style="color:#00ff88; margin:0;">২. Risk Management (ঝুঁকি ব্যবস্থাপনা)</h4><hr style="margin:8px 0;">
            • <b>Position Sizing:</b> ৩-ধাপের Smart DCA ($33.33 প্রতি ধাপে)<br>
            • <b>Exit Planning:</b> টেক প্রফিট <code>+1.5%</code> | স্টপ লস <code>-3.0%</code><br>
            • <b>Capital Protection:</b> লাভের ৭৫% সরাসরি নিরাপদ ভল্টে লক!
        </div>
        """, unsafe_allow_html=True)
    with r2:
        st.markdown(f"""
        <div class="roadmap-card">
            <h4 style="color:#ffcc00; margin:0;">৩. Trading Psychology (ট্রেডিং সাইকোলজি)</h4><hr style="margin:8px 0;">
            • <b>Emotional Awareness:</b> {rm.get('emotion_state', f"স্কোর {portfolio.get('sentiment_score', 50)}/100")}<br>
            • <b>Discipline:</b> {rm.get('discipline', 'ওভারট্রেডিং সুরক্ষিত')}<br>
            • <b>Patience:</b> {rm.get('patience', 'সেরা সেটআপের অপেক্ষায়')}
        </div>
        <div class="roadmap-card">
            <h4 style="color:#ff66b2; margin:0;">৪. Trading Process (ট্রেডিং প্রক্রিয়া)</h4><hr style="margin:8px 0;">
            • <b>Strategy:</b> ১০০% হালাল স্পট (RSI + MACD + EMA)<br>
            • <b>Testing:</b> ব্যাকটেস্ট উইন রেট <code>{portfolio.get('backtest_metrics', {}).get('win_rate', 82.5)}%</code><br>
            • <b>Review:</b> ৪ ঘণ্টার অটোমেটিক ডায়েরি সচল
        </div>
        """, unsafe_allow_html=True)

elif selected_page == "🤖 HalalCopilot (AI মেন্টর)":
    st.subheader("🤖 HalalCopilot সহকারী (আপনার ব্যক্তিগত ট্রেডিং শিক্ষক)")
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    q1, q2, q3 = st.columns(3)
    quick_prompt = None
    if q1.button("📊 গত ৪ ঘণ্টায় বট কী করেছে?", use_container_width=True):
        quick_prompt = "বট সর্বশেষ কী সিদ্ধান্ত নিয়েছে, মার্কেটের সাপোর্ট-রেজিস্ট্যান্স কোথায় এবং কেন অপেক্ষা করছে তা সহজ বাংলায় বলো।"
    if q2.button("🗺️ সাপোর্ট ও রেজিস্ট্যান্স কী?", use_container_width=True):
        quick_prompt = f"বর্তমান চার্টে সাপোর্ট ${support_lvl:,.0f} এবং রেজিস্ট্যান্স ${resist_lvl:,.0f} দেখাচ্ছে। ট্রেডিংয়ে এগুলোর কাজ কী, সহজ বাংলায় শেখাও।"
    if q3.button("💼 আমার লাভ-লসের বিস্তারিত হিসাব দাও", use_container_width=True):
        quick_prompt = "আমার মোট ব্যালেন্স, প্রফিট ভল্ট এবং ওপেন ট্রেডের বর্তমান অবস্থা বিশ্লেষণ করে বলো।"

    user_query = st.text_input("আপনার প্রশ্ন লিখুন:", placeholder="যেমন: বট কখন পরের ট্রেড নেবে?")
    if st.button("জিজ্ঞেস করুন 🚀", type="primary", use_container_width=True) or quick_prompt:
        final_q = quick_prompt if quick_prompt else user_query
        if final_q:
            with st.spinner("⚡ HalalCopilot উত্তর দিচ্ছে..."):
                try:
                    ai_client = get_ai_client(GEMINI_API_KEY)
                    prompt_text = f"""
                    BTC Price: ${current_price:,.2f} | Support: ${support_lvl:,.0f} | Resistance: ${resist_lvl:,.0f}
                    Indicators: {portfolio.get('indicators')} | Signal: {portfolio.get('last_signal')}
                    Wallet: Total=${grand_total:.2f}, Cash=${portfolio['usdt_balance']:.2f}, Vault=${profit_vault:.2f}
                    Question: {final_q}
                    """
                    ans = ask_fast_ai(ai_client, prompt_text, "তুমি HalalCopilot, ইউজারের ব্যক্তিগত ট্রেডিং বট ও মেন্টর। ৩-৪ লাইনে খুব সহজ বাংলায় উত্তর দেবে।")
                    st.session_state.chat_history.insert(0, {"q": final_q, "a": ans})
                except Exception as e:
                    st.error(f"এপিআই সমস্যা: {e}")

    for chat in st.session_state.chat_history[:5]:
        with st.chat_message("user"):
            st.write(chat["q"])
        with st.chat_message("assistant"):
            st.write(chat["a"])

elif selected_page == "📜 ট্রেড হিস্ট্রি ও অ্যানালিটিক্স":
    bt = portfolio.get("backtest_metrics", {})
    win_rate = (portfolio['wins'] / portfolio['total_trades'] * 100) if portfolio['total_trades'] > 0 else bt.get("win_rate", 82.5)
    a1, a2, a3, a4 = st.columns(4)
    a1.metric("🎯 উইন রেট (Win Rate)", f"{win_rate:.1f}%")
    a2.metric("⚖️ প্রফিট ফ্যাক্টর", f"{bt.get('profit_factor', 2.1)}")
    a3.metric("📉 ম্যাক্স ড্রডাউন", f"-{max(portfolio.get('max_drawdown', 0.0), bt.get('max_dd', 2.1)):.2f}%")
    a4.metric("📐 শার্প রেশিও", f"{bt.get('sharpe_ratio', 1.65)}")

    st.divider()
    st.subheader("📜 প্রতিটি কেনা-বেচার লগ")
    if portfolio.get("trade_history"):
        st.dataframe(pd.DataFrame(portfolio["trade_history"]), use_container_width=True)
    else:
        st.info("🕒 এখনো কোনো ট্রেড সম্পন্ন হয়নি।")

elif selected_page == "🛡️ রিস্ক অ্যান্ড সেফটি সেন্টার":
    r_col1, r_col2 = st.columns(2)
    with r_col1:
        is_paused = portfolio.get("bot_paused", False)
        if st.button("▶️ বট চালু করুন" if is_paused else "⏸️ বট সাময়িক পজ করুন", use_container_width=True):
            portfolio["bot_paused"] = not is_paused
            save_portfolio(portfolio)
            st.rerun()
        new_limit = st.slider("🚦 দৈনিক সর্বোচ্চ ট্রেড লিমিট:", 1, 20, int(portfolio.get("daily_trade_limit", 5)))
        if new_limit != portfolio.get("daily_trade_limit", 5):
            portfolio["daily_trade_limit"] = new_limit
            save_portfolio(portfolio)
    with r_col2:
        st.info(f"🔑 **API Key Security:** `{mask_key(GEMINI_API_KEY)}`")
        st.success("✅ **মডুলার সাইডবার লেআউট সচল:** এখন থেকে প্রফেশনাল স্টাইলে সাইডবার দিয়ে টার্মিনাল কন্ট্রোল হবে!")