import streamlit as st
import mysql.connector
import pandas as pd
import plotly.express as px
from datetime import datetime
import os

# --- PAGE CONFIG ---
st.set_page_config(page_title="Amore Financial Cloud", layout="wide", page_icon="🏠")

# --- DATABASE & AUTH CONFIGURATION ---
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
    DB_CONFIG = None
    APP_PASSWORD = "admin"

def get_connection():
    if DB_CONFIG:
        return mysql.connector.connect(**DB_CONFIG)
    return None

# --- INITIALIZE DATABASE TABLES ---
def init_db():
    conn = get_connection()
    if conn:
        cursor = conn.cursor()
        # Create expenses table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INT AUTO_INCREMENT PRIMARY KEY,
                category VARCHAR(255),
                amount DECIMAL(10,2),
                bill_date DATE,
                description TEXT
            )
        """)
        conn.commit()
        conn.close()

init_db()

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
    .main-header { background-color: #507d00; padding: 20px; border-radius: 15px; color: white; text-align: center; margin-bottom: 20px; }
    .stMetric { background-color: white; padding: 15px; border-radius: 12px; border: 1px solid #f0f2f6; }
    </style>
    <div class="main-header">
        <h1 style="margin:0;">AMORE FINANCIAL TRACKER</h1>
    </div>
    """, unsafe_allow_html=True)

# --- DATA FETCHING ---
def fetch_data():
    conn = get_connection()
    if conn:
        try:
            tenants_df = pd.read_sql("SELECT * FROM bookings", conn)
            expenses_df = pd.read_sql("SELECT * FROM expenses", conn)
            conn.close()
            return tenants_df, expenses_df
        except:
            conn.close()
    return pd.DataFrame(), pd.DataFrame()

tenants, expenses = fetch_data()

# --- SIDEBAR ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/619/619034.png", width=100)
    st.write(f"User: **Business Admin**")
    menu = st.radio("Navigate", ["Dashboard", "Data Entry", "Utility Analysis", "Sync Settings"])
    if st.button("Logout", use_container_width=True):
        st.session_state.logged_in = False
        st.rerun()

# --- DASHBOARD ---
if menu == "Dashboard":
    if not tenants.empty:
        total_rev = len(tenants[tenants['status'] != 'Checked-out']) * 8500 # Simple estimate
        total_exp = expenses['amount'].sum() if not expenses.empty else 0
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Gross Revenue", f"₱{total_rev:,.0f}")
        m2.metric("Total Expenses", f"₱{total_exp:,.0f}")
        m3.metric("Net Profit", f"₱{(total_rev - total_exp):,.0f}")
        m4.metric("Active Units", tenants['unit_room'].nunique())

        st.divider()
        col_left, col_right = st.columns([2, 1])
        with col_left:
            st.subheader("📋 Booking Ledger")
            st.dataframe(tenants[['unit_room', 'guest_name', 'status', 'checkin_date']].tail(10), use_container_width=True, hide_index=True)
        with col_right:
            st.subheader("📊 Expense Mix")
            if not expenses.empty:
                fig = px.pie(expenses, values='amount', names='category', hole=0.4, color_discrete_sequence=['#507d00', '#88b04b', '#ffc107', '#6c757d'])
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Add expenses in 'Data Entry' to see charts.")

# --- DATA ENTRY ---
elif menu == "Data Entry":
    st.subheader("➕ Enter Amore Monthly Expenses")
    with st.form("expense_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        category = col1.selectbox("Category", ["Electricity", "Water", "Internet", "Maintenance", "Staff Salary", "Other"])
        amount = col2.number_input("Amount (₱)", min_value=0.0, step=100.0)
        bill_date = st.date_input("Billing Date")
        description = st.text_area("Description (Optional)")
        
        if st.form_submit_button("Save Expense to Cloud"):
            if amount > 0:
                conn = get_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO expenses (category, amount, bill_date, description) VALUES (%s, %s, %s, %s)", 
                                 (category, amount, bill_date, description))
                    conn.commit()
                    conn.close()
                    st.success(f"Saved ₱{amount:,.2f} for {category}")
                    st.rerun()
            else:
                st.warning("Please enter an amount greater than 0.")

    st.divider()
    st.subheader("🗑️ Manage Existing Expenses")
    if not expenses.empty:
        st.dataframe(expenses, use_container_width=True, hide_index=True)
        if st.button("Clear All Expenses (Careful!)"):
            conn = get_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM expenses")
                conn.commit(); conn.close()
                st.rerun()

# --- UTILITY ANALYSIS ---
elif menu == "Utility Analysis":
    st.subheader("⚡ Utility Recovery Tracking")
    if not expenses.empty:
        bill_elec = expenses[expenses['category'] == 'Electricity']['amount'].sum()
        # Mock recovery logic: ₱1,200 per active room
        recovered_elec = len(tenants[tenants['status'] != 'Checked-out']) * 1200 
        
        c1, c2 = st.columns(2)
        with c1:
            st.write("#### Electricity")
            st.metric("Paid to Utility Co.", f"₱{bill_elec:,.0f}")
            st.metric("Recovered from Tenants", f"₱{recovered_elec:,.0f}", f"{recovered_elec - bill_elec:,.0f}")
            st.progress(min(recovered_elec / bill_elec, 1.0) if bill_elec > 0 else 0)
    else:
        st.info("Enter your Electricity/Water bills in 'Data Entry' to see the recovery analysis.")

# --- SETTINGS ---
elif menu == "Sync Settings":
    st.subheader("⚙️ System Status")
    st.success(f"Database: {DB_CONFIG['host']}" if DB_CONFIG else "Running Offline/Local")
    if st.button("Force Refresh All Data"):
        st.cache_data.clear()
        st.rerun()

st.caption("Amore Financial Cloud v1.1")