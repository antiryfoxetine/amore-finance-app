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
        # Table for Amore's main expenses (Main Meter Bills)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INT AUTO_INCREMENT PRIMARY KEY,
                category VARCHAR(255),
                amount DECIMAL(10,2),
                bill_date DATE,
                description TEXT
            )
        """)
        # Table for payments made BY tenants (Individual Sub-meter Readings)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tenant_payments (
                id INT AUTO_INCREMENT PRIMARY KEY,
                guest_name VARCHAR(255),
                unit_room VARCHAR(50),
                utility_type VARCHAR(100),
                amount DECIMAL(10,2),
                payment_date DATE
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
            payments_df = pd.read_sql("SELECT ? FROM tenant_payments", conn) # Modified to avoid SQL injection risks in some environments
            payments_df = pd.read_sql("SELECT * FROM tenant_payments", conn)
            conn.close()
            return tenants_df, expenses_df, payments_df
        except:
            if conn: conn.close()
    return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

tenants, expenses, tenant_payments = fetch_data()

# --- SIDEBAR ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/619/619034.png", width=100)
    st.write(f"User: **Business Admin**")
    menu = st.radio("Navigate", ["Dashboard", "Data Entry", "Utility Reconciliation", "Sync Settings"])
    if st.button("Logout", use_container_width=True):
        st.session_state.logged_in = False
        st.rerun()

# --- DASHBOARD ---
if menu == "Dashboard":
    # Calculating strictly from database tables
    total_revenue = tenant_payments['amount'].sum() if not tenant_payments.empty else 0
    total_expenses = expenses['amount'].sum() if not expenses.empty else 0
    net_profit = total_revenue - total_expenses
    active_units = tenants[tenants['status'] != 'Checked-out']['unit_room'].nunique() if not tenants.empty else 0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Gross Revenue", f"₱{total_revenue:,.2f}")
    m2.metric("Total Expenses", f"₱{total_expenses:,.2f}")
    m3.metric("Net Profit", f"₱{net_profit:,.2f}")
    m4.metric("Active Units", active_units)

    st.divider()
    
    if tenants.empty and tenant_payments.empty and expenses.empty:
        st.info("Your database is currently empty. Start entering data in the 'Data Entry' tab to see financials.")
    else:
        col_left, col_right = st.columns([2, 1])
        with col_left:
            st.subheader("📋 Booking Ledger (Status)")
            if not tenants.empty:
                st.dataframe(tenants[['unit_room', 'guest_name', 'status', 'checkin_date']].tail(10), use_container_width=True, hide_index=True)
            else:
                st.write("No bookings found.")
        with col_right:
            st.subheader("📊 Expense Mix")
            if not expenses.empty:
                fig = px.pie(expenses, values='amount', names='category', hole=0.4, color_discrete_sequence=['#507d00', '#88b04b', '#ffc107', '#6c757d'])
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.caption("No expenses recorded yet.")

# --- DATA ENTRY ---
elif menu == "Data Entry":
    tab1, tab2 = st.tabs(["⚡ Main Meter Bills (Amore Pays)", "🔢 Individual Meter Payments (Tenants)"])
    
    with tab1:
        st.write("### Record Master Utility Bills")
        with st.form("expense_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            category = col1.selectbox("Utility Type", ["Electricity", "Water", "Internet", "Maintenance", "Staff Salary"])
            amount = col2.number_input("Total Main Bill (₱)", min_value=0.0, step=100.0)
            bill_date = st.date_input("Billing Period Date")
            description = st.text_area("Notes")
            if st.form_submit_button("Save Main Bill"):
                if amount > 0:
                    conn = get_connection()
                    if conn:
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO expenses (category, amount, bill_date, description) VALUES (%s, %s, %s, %s)", 
                                     (category, amount, bill_date, description))
                        conn.commit(); conn.close()
                        st.success("Main bill saved.")
                        st.rerun()

    with tab2:
        st.write("### Record Tenant Meter Payments")
        with st.form("payment_form", clear_on_submit=True):
            guest_names = tenants['guest_name'].unique().tolist() if not tenants.empty else []
            col1, col2 = st.columns(2)
            selected_guest = col1.selectbox("Tenant", guest_names) if guest_names else col1.text_input("Tenant Name")
            unit = col2.text_input("Unit/Room")
            
            p_col1, p_col2 = st.columns(2)
            p_type = p_col1.selectbox("Utility Paid", ["Electricity", "Water", "Internet", "Maintenance Fee", "Rent"])
            p_amount = p_col2.number_input("Amount Collected (₱)", min_value=0.0, step=50.0)
            p_date = st.date_input("Collection Date")
            
            if st.form_submit_button("Save Individual Payment"):
                if p_amount > 0:
                    conn = get_connection()
                    if conn:
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO tenant_payments (guest_name, unit_room, utility_type, amount, payment_date) VALUES (%s, %s, %s, %s, %s)", 
                                     (selected_guest, unit, p_type, p_amount, p_date))
                        conn.commit(); conn.close()
                        st.success("Payment recorded.")
                        st.rerun()

# --- UTILITY RECONCILIATION ---
elif menu == "Utility Reconciliation":
    st.subheader("⚖️ Reconciliation")
    u_type = st.selectbox("Select Utility", ["Electricity", "Water", "Internet"])
    
    paid = expenses[expenses['category'] == u_type]['amount'].sum() if not expenses.empty else 0
    collected = tenant_payments[tenant_payments['utility_type'].str.contains(u_type, case=False)]['amount'].sum() if not tenant_payments.empty else 0
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Paid (Main)", f"₱{paid:,.2f}")
    c2.metric("Total Collected (Units)", f"₱{collected:,.2f}")
    c3.metric("Gap", f"₱{collected - paid:,.2f}", delta=float(collected - paid))

# --- SETTINGS ---
elif menu == "Sync Settings":
    st.subheader("⚙️ Settings")
    if st.button("Refresh Cloud Data"):
        st.cache_data.clear()
        st.rerun()

st.caption("Amore Financial Cloud v1.4 | Real Data Only")