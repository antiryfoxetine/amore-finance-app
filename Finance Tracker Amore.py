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
            payments_df = pd.read_sql("SELECT * FROM tenant_payments", conn)
            conn.close()
            return tenants_df, expenses_df, payments_df
        except:
            conn.close()
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
    if not tenants.empty:
        # Base Rent Revenue + Utility Collections
        base_rent = len(tenants[tenants['status'] != 'Checked-out']) * 8500 
        utility_collected = tenant_payments['amount'].sum() if not tenant_payments.empty else 0
        total_rev = base_rent + utility_collected
        
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
                st.info("Add bills to see charts.")

# --- DATA ENTRY ---
elif menu == "Data Entry":
    tab1, tab2 = st.tabs(["⚡ Main Meter Bills (Amore Pays)", "🔢 Individual Meter Payments (Tenants)"])
    
    with tab1:
        st.write("### Record Master Utility Bills")
        st.caption("Enter the total amount from the main electric/water meters.")
        with st.form("expense_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            category = col1.selectbox("Utility Type", ["Electricity", "Water", "Internet", "Maintenance", "Staff Salary"])
            amount = col2.number_input("Total Main Bill (₱)", min_value=0.0, step=100.0)
            bill_date = st.date_input("Billing Period Date")
            description = st.text_area("Notes (e.g., 'May 2024 Main Meter')")
            
            if st.form_submit_button("Save Main Bill"):
                if amount > 0:
                    conn = get_connection()
                    if conn:
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO expenses (category, amount, bill_date, description) VALUES (%s, %s, %s, %s)", 
                                     (category, amount, bill_date, description))
                        conn.commit(); conn.close()
                        st.success(f"Main {category} bill of ₱{amount:,.2f} recorded.")
                        st.rerun()

    with tab2:
        st.write("### Record Tenant Meter Payments")
        st.caption("Record individual payments based on unit sub-meter readings.")
        with st.form("payment_form", clear_on_submit=True):
            guest_list = tenants['guest_name'].unique().tolist() if not tenants.empty else []
            col1, col2 = st.columns(2)
            
            if guest_list:
                selected_guest = col1.selectbox("Select Tenant", guest_list)
                guess_unit = tenants[tenants['guest_name'] == selected_guest]['unit_room'].iloc[0]
            else:
                selected_guest = col1.text_input("Tenant Name")
                guess_unit = ""
                
            unit = col2.text_input("Unit/Room", value=guess_unit)
            
            p_col1, p_col2 = st.columns(2)
            p_type = p_col1.selectbox("Utility Paid", ["Electricity", "Water", "Internet", "Maintenance Fee"])
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
                        st.success(f"Individual payment of ₱{p_amount:,.2f} saved.")
                        st.rerun()

# --- UTILITY RECONCILIATION ---
elif menu == "Utility Reconciliation":
    st.subheader("⚖️ Master Meter vs. Individual Meters")
    st.write("Compare your main bills against what was collected from tenants.")
    
    u_type = st.selectbox("Analyze Recovery For:", ["Electricity", "Water", "Internet"])
    
    total_paid = expenses[expenses['category'] == u_type]['amount'].sum() if not expenses.empty else 0
    total_collected = tenant_payments[tenant_payments['utility_type'].str.contains(u_type, case=False)]['amount'].sum() if not tenant_payments.empty else 0
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Main Meter Bill (Total Paid)", f"₱{total_paid:,.0f}")
    c2.metric("Unit Meters (Total Collected)", f"₱{total_collected:,.0f}")
    
    gap = total_collected - total_paid
    status_color = "normal" if gap >= 0 else "inverse"
    c3.metric("Reconciliation Gap", f"₱{gap:,.0f}", delta=float(gap), delta_color=status_color)
    
    st.divider()
    
    if total_paid > 0:
        recovery_pct = (total_collected / total_paid) * 100
        st.write(f"#### {u_type} Recovery Progress: {recovery_pct:.1f}%")
        st.progress(min(total_collected / total_paid, 1.0))
        
        if recovery_pct < 90:
            st.warning(f"⚠️ Warning: Your {u_type} collections are significantly lower than the main bill. Check for leaks, common area usage, or unrecorded meter readings.")
        elif recovery_pct >= 100:
            st.success(f"✅ Success: Your {u_type} costs are fully covered by tenant sub-meters.")
        else:
            st.info(f"💡 You are covering ₱{abs(gap):,.0f} of the building's {u_type} costs.")

# --- SETTINGS ---
elif menu == "Sync Settings":
    st.subheader("⚙️ Cloud Configuration")
    st.success(f"Linked to Aiven MySQL: {DB_CONFIG['host']}" if DB_CONFIG else "Running in Local Mode")
    if st.button("Force Refresh All Cloud Data"):
        st.cache_data.clear()
        st.rerun()

st.caption("Amore Financial Cloud v1.3 | Sub-meter Reconciliation Enabled")