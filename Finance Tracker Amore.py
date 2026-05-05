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
        # Table for Amore's main expenses (Main Meter Bills, Salaries, etc.)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INT AUTO_INCREMENT PRIMARY KEY,
                category VARCHAR(255),
                amount DECIMAL(10,2),
                bill_date DATE,
                description TEXT
            )
        """)
        # Table for all payments made by tenants
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tenant_payments (
                id INT AUTO_INCREMENT PRIMARY KEY,
                guest_name VARCHAR(255),
                unit_room VARCHAR(50),
                payment_type VARCHAR(100), -- 'Rent' or 'Utility'
                sub_category VARCHAR(100), -- 'Electricity', 'Water', 'Internet', etc.
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
    # Splitting Revenue
    rent_total = tenant_payments[tenant_payments['payment_type'] == 'Rent']['amount'].sum() if not tenant_payments.empty else 0
    util_total = tenant_payments[tenant_payments['payment_type'] == 'Utility']['amount'].sum() if not tenant_payments.empty else 0
    
    total_revenue = rent_total + util_total
    total_expenses = expenses['amount'].sum() if not expenses.empty else 0
    net_profit = total_revenue - total_expenses
    active_units = tenants[tenants['status'] != 'Checked-out']['unit_room'].nunique() if not tenants.empty else 0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Rent Collected", f"₱{rent_total:,.2f}")
    m2.metric("Utility Collected", f"₱{util_total:,.2f}")
    m3.metric("Net Profit", f"₱{net_profit:,.2f}")
    m4.metric("Active Units", active_units)

    st.divider()
    
    if tenants.empty and tenant_payments.empty and expenses.empty:
        st.info("Database is empty. Please enter data in the 'Data Entry' tab.")
    else:
        col_left, col_right = st.columns([2, 1])
        with col_left:
            st.subheader("📊 Revenue Composition")
            rev_data = pd.DataFrame({
                'Source': ['Base Rent', 'Utilities'],
                'Amount': [rent_total, util_total]
            })
            fig_rev = px.bar(rev_data, x='Source', y='Amount', color='Source', 
                             color_discrete_map={'Base Rent': '#507d00', 'Utilities': '#ffc107'})
            st.plotly_chart(fig_rev, use_container_width=True)
            
        with col_right:
            st.subheader("📋 Recent Payments")
            if not tenant_payments.empty:
                st.dataframe(tenant_payments[['guest_name', 'payment_type', 'amount', 'payment_date']].tail(5), 
                             use_container_width=True, hide_index=True)

# --- DATA ENTRY ---
elif menu == "Data Entry":
    tab_exp, tab_rent, tab_util = st.tabs(["⚡ Main Bills (Amore Pays)", "🏠 Rent Collection", "🔢 Meter Payments (Tenants)"])
    
    with tab_exp:
        st.write("### Record Master Utility Bills")
        with st.form("expense_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            category = col1.selectbox("Utility Type", ["Electricity", "Water", "Internet", "Maintenance", "Staff Salary"])
            amount = col2.number_input("Total Main Bill (₱)", min_value=0.0, step=100.0)
            bill_date = st.date_input("Billing Period Date")
            if st.form_submit_button("Save Main Bill"):
                if amount > 0:
                    conn = get_connection()
                    if conn:
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO expenses (category, amount, bill_date) VALUES (%s, %s, %s)", (category, amount, bill_date))
                        conn.commit(); conn.close()
                        st.success("Main bill saved.")
                        st.rerun()

    with tab_rent:
        st.write("### Record Tenant Rent")
        guest_names = tenants['guest_name'].unique().tolist() if not tenants.empty else []
        selected_guest = st.selectbox("Select Tenant Name", guest_names) if guest_names else st.text_input("Tenant Name")
        
        # Auto-lookup unit based on selection
        auto_unit = ""
        if not tenants.empty and selected_guest in guest_names:
            auto_unit = tenants[tenants['guest_name'] == selected_guest]['unit_room'].iloc[0]

        with st.form("rent_form", clear_on_submit=True):
            unit = st.text_input("Unit/Room", value=auto_unit, key="rent_unit")
            r_amount = st.number_input("Monthly Rent Amount (₱)", min_value=0.0, step=500.0)
            r_date = st.date_input("Payment Date", key="rent_date")
            
            if st.form_submit_button("Save Rent Payment"):
                if r_amount > 0 and selected_guest:
                    conn = get_connection()
                    if conn:
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO tenant_payments (guest_name, unit_room, payment_type, sub_category, amount, payment_date) VALUES (%s, %s, %s, %s, %s, %s)", 
                                     (selected_guest, unit, 'Rent', 'Monthly Rent', r_amount, r_date))
                        conn.commit(); conn.close()
                        st.success(f"Rent recorded for {selected_guest} (Unit {unit}).")
                        st.rerun()
                else:
                    st.warning("Please ensure tenant name is provided and amount is greater than 0.")

    with tab_util:
        st.write("### Record Sub-meter Payments")
        guest_names = tenants['guest_name'].unique().tolist() if not tenants.empty else []
        
        col_select, col_empty = st.columns([1, 1])
        selected_guest_u = col_select.selectbox("Select Tenant Name", guest_names, key="u_guest_sel") if guest_names else col_select.text_input("Tenant Name", key="u_guest_text")
        
        # Auto-lookup unit based on selection
        auto_unit_u = ""
        if not tenants.empty and selected_guest_u in guest_names:
            auto_unit_u = tenants[tenants['guest_name'] == selected_guest_u]['unit_room'].iloc[0]

        with st.form("util_payment_form", clear_on_submit=True):
            unit_u = st.text_input("Unit/Room", value=auto_unit_u, key="u_unit")
            p_col1, p_col2 = st.columns(2)
            p_type = p_col1.selectbox("Utility Type", ["Electricity (Sub-meter)", "Water (Sub-meter)", "Internet", "Maintenance Fee"])
            p_amount = p_col2.number_input("Amount Collected (₱)", min_value=0.0, step=50.0)
            p_date = st.date_input("Collection Date", key="u_date")
            
            if st.form_submit_button("Save Utility Payment"):
                if p_amount > 0 and selected_guest_u:
                    conn = get_connection()
                    if conn:
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO tenant_payments (guest_name, unit_room, payment_type, sub_category, amount, payment_date) VALUES (%s, %s, %s, %s, %s, %s)", 
                                     (selected_guest_u, unit_u, 'Utility', p_type, p_amount, p_date))
                        conn.commit(); conn.close()
                        st.success(f"{p_type} payment saved for {selected_guest_u}.")
                        st.rerun()
                else:
                    st.warning("Please ensure tenant name is provided and amount is greater than 0.")

# --- UTILITY RECONCILIATION ---
elif menu == "Utility Reconciliation":
    st.subheader("⚖️ Master Meter vs. Individual Meter Collections")
    u_type = st.selectbox("Select Utility to Reconcile", ["Electricity", "Water", "Internet"])
    
    paid = expenses[expenses['category'] == u_type]['amount'].sum() if not expenses.empty else 0
    # Match the sub-meter category names
    search_term = u_type
    collected = tenant_payments[(tenant_payments['payment_type'] == 'Utility') & (tenant_payments['sub_category'].str.contains(search_term, case=False))]['amount'].sum() if not tenant_payments.empty else 0
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Main Bill Total", f"₱{paid:,.2f}")
    c2.metric("Total from Sub-meters", f"₱{collected:,.2f}")
    c3.metric("Balance", f"₱{collected - paid:,.2f}", delta=float(collected - paid))

# --- SETTINGS ---
elif menu == "Sync Settings":
    st.subheader("⚙️ Settings")
    if st.button("Refresh Cloud Data"):
        st.cache_data.clear()
        st.rerun()

st.caption("Amore Financial Cloud v1.6 | Auto-sync Unit Numbers")