import streamlit as st
import mysql.connector
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import os

# --- PAGE CONFIG ---
st.set_page_config(page_title="Amore Financial Cloud", layout="wide", page_icon="🏠")

# --- DATABASE & AUTH CONFIGURATION (SECURE) ---
try:
    DB_CONFIG = {
        'host': st.secrets["mysql"]["host"],
        'port': int(st.secrets["mysql"]["port"]),
        'user': st.secrets["mysql"]["user"],
        'password': st.secrets["mysql"]["password"],
        'database': st.secrets["mysql"]["database"]
    }
    APP_PASSWORD = st.secrets["auth"]["password"]
except Exception:
    # Providing default/demo values for local testing if secrets aren't set yet
    DB_CONFIG = None
    APP_PASSWORD = "admin" # Default for preview

def get_connection():
    if DB_CONFIG:
        return mysql.connector.connect(**DB_CONFIG)
    return None

# --- LOGIN LOGIC ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    col_l1, col_l2, col_l3 = st.columns([1, 1, 1])
    with col_l2:
        st.markdown("<h1 style='text-align: center;'>🏠</h1>", unsafe_allow_html=True)
        st.markdown("""
            <div style="text-align: center; padding-bottom: 20px;">
                <h1 style="color: #507d00; font-family: 'Segoe UI', sans-serif; margin-top: 0;">AMORE FINANCE</h1>
                <p style="color: #666;">Secure Financial Portal</p>
            </div>
        """, unsafe_allow_html=True)
        with st.form("login_form"):
            pwd = st.text_input("Enter Staff Password", type="password")
            if st.form_submit_button("Access Financials", use_container_width=True):
                if pwd == APP_PASSWORD:
                    st.session_state.logged_in = True
                    st.rerun()
                else:
                    st.error("Incorrect password.")
    st.stop()

# --- CUSTOM STYLING ---
st.markdown("""
    <style>
    .main-header {
        background-color: #507d00;
        padding: 25px;
        border-radius: 15px;
        color: white;
        text-align: center;
        margin-bottom: 25px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .stMetric {
        background-color: white;
        padding: 15px;
        border-radius: 12px;
        border: 1px solid #f0f2f6;
    }
    </style>
    <div class="main-header">
        <h1 style="margin:0;">AMORE FINANCIAL TRACKER</h1>
        <p style="margin:0; opacity: 0.8;">Earnings, Expenses & Utility Recovery</p>
    </div>
    """, unsafe_allow_html=True)

# --- DATA FETCHING ---
@st.cache_data(ttl=600)
def fetch_finance_data():
    """Fetches data with a fallback to demo data if connection fails."""
    try:
        conn = get_connection()
        if conn:
            tenants_df = pd.read_sql("SELECT * FROM bookings", conn)
            try:
                expenses_df = pd.read_sql("SELECT * FROM expenses", conn)
            except:
                expenses_df = pd.DataFrame([
                    {"category": "Electricity", "amount": 14200, "date": "2024-05-15"},
                    {"category": "Water", "amount": 3100, "date": "2024-05-16"},
                    {"category": "Internet", "amount": 2500, "date": "2024-05-17"},
                    {"category": "Maintenance", "amount": 1200, "date": "2024-05-18"},
                ])
            conn.close()
            return tenants_df, expenses_df
    except Exception:
        pass
    
    # DEMO DATA FALLBACK
    tenants_mock = pd.DataFrame([
        {"unit_room": "101", "guest_name": "Juana Dela Cruz", "status": "Long-term", "checkin_date": "01-10-2024"},
        {"unit_room": "102", "guest_name": "Marcus Aurelius", "status": "Checked-in", "checkin_date": "05-15-2024"},
        {"unit_room": "201", "guest_name": "Elena Gilbert", "status": "Reserved", "checkin_date": "05-20-2024"},
        {"unit_room": "202", "guest_name": "Damon Salvatore", "status": "Long-term", "checkin_date": "02-14-2024"},
    ])
    expenses_mock = pd.DataFrame([
        {"category": "Electricity", "amount": 15000, "date": "2024-05-01"},
        {"category": "Water", "amount": 3500, "date": "2024-05-01"},
        {"category": "Internet", "amount": 2500, "date": "2024-05-01"},
        {"category": "Maintenance", "amount": 2000, "date": "2024-05-05"},
    ])
    return tenants_mock, expenses_mock

tenants, expenses = fetch_finance_data()

# --- SIDEBAR ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/619/619034.png", width=100)
    st.write(f"User: **Business Admin**")
    menu = st.radio("Navigate", ["Dashboard", "Utility Analysis", "Sync Settings"])
    
    if st.button("Logout", use_container_width=True):
        st.session_state.logged_in = False
        st.rerun()
    st.divider()
    st.caption(f"Last synced: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

if menu == "Dashboard":
    if not tenants.empty:
        lt_tenants = tenants[tenants['status'] == 'Long-term']
        st_tenants = tenants[tenants['status'].isin(['Checked-in', 'Reserved'])]
        
        # Calculation Logic (Demo rates)
        total_rev = (len(lt_tenants) * 8500) + (len(st_tenants) * 1500)
        total_exp = expenses['amount'].sum()
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Gross Revenue", f"₱{total_rev:,.0f}")
        m2.metric("Total Expenses", f"₱{total_exp:,.0f}")
        m3.metric("Net Profit", f"₱{(total_rev - total_exp):,.0f}")
        m4.metric("Active Units", tenants['unit_room'].nunique())

        st.divider()
        
        col_left, col_right = st.columns([2, 1])
        
        with col_left:
            st.subheader("📋 Recent Booking Data")
            st.dataframe(tenants[['unit_room', 'guest_name', 'status', 'checkin_date']], use_container_width=True, hide_index=True)
            
        with col_right:
            st.subheader("📊 Expense Mix")
            fig = px.pie(expenses, values='amount', names='category', hole=0.4, 
                         color_discrete_sequence=['#507d00', '#88b04b', '#ffc107', '#6c757d'])
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Waiting for data sync...")

elif menu == "Utility Analysis":
    st.subheader("⚡ Utility Recovery Tracking")
    st.write("Compare main bill payments vs. tenant contributions.")
    
    # Recovery Logic
    bill_elec = expenses[expenses['category'] == 'Electricity']['amount'].sum() or 15000
    recovered_elec = (len(tenants[tenants['status'] != 'Checked-out']) * 1200) 
    
    c1, c2 = st.columns(2)
    with c1:
        st.write("#### Electricity")
        st.metric("Recovery", f"₱{recovered_elec:,.0f}", f"{recovered_elec - bill_elec:,.0f} Gap")
        st.progress(min(recovered_elec / bill_elec, 1.0) if bill_elec > 0 else 0)
        
    with c2:
        st.write("#### Water")
        bill_water = expenses[expenses['category'] == 'Water']['amount'].sum() or 3500
        recovered_water = (len(tenants[tenants['status'] != 'Checked-out']) * 350)
        st.metric("Recovery", f"₱{recovered_water:,.0f}", f"{recovered_water - bill_water:,.0f} Gap")
        st.progress(min(recovered_water / bill_water, 1.0) if bill_water > 0 else 0)

elif menu == "Sync Settings":
    st.subheader("⚙️ Connection Status")
    if DB_CONFIG:
        st.success(f"Connected to Aiven MySQL: {DB_CONFIG['host']}")
    else:
        st.warning("Running in Demo Mode. Connect your Aiven DB via Streamlit Secrets.")
    
    if st.button("Force Refresh Data"):
        st.cache_data.clear()
        st.rerun()

st.divider()
st.caption("Amore Financial Cloud v1.0 | Professional Edition")