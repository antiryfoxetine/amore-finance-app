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
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INT AUTO_INCREMENT PRIMARY KEY,
                category VARCHAR(255),
                amount DECIMAL(10,2),
                bill_date DATE,
                description TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tenant_payments (
                id INT AUTO_INCREMENT PRIMARY KEY,
                guest_name VARCHAR(255),
                unit_room VARCHAR(50),
                payment_type VARCHAR(100), 
                sub_category VARCHAR(100), 
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

# --- DATA FETCHING (WITH CACHING TO FIX SLOWNESS) ---
@st.cache_data(ttl=600)
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

# Chart Config for Downloads
CHART_CONFIG = {
    'displayModeBar': True,
    'toImageButtonOptions': {
        'format': 'png',
        'filename': 'amore_financial_report',
        'height': 600,
        'width': 1000,
        'scale': 2
    }
}

# --- SIDEBAR ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/619/619034.png", width=100)
    st.write(f"User: **Business Admin**")
    menu = st.radio("Navigate", ["Dashboard", "Data Entry", "Utility Reconciliation", "Reports & Export", "Sync Settings"])
    if st.button("Logout", use_container_width=True):
        st.session_state.logged_in = False
        st.rerun()

# --- DASHBOARD ---
if menu == "Dashboard":
    rent_total = tenant_payments[tenant_payments['payment_type'] == 'Rent']['amount'].sum() if not tenant_payments.empty else 0
    util_total = tenant_payments[tenant_payments['payment_type'] == 'Utility']['amount'].sum() if not tenant_payments.empty else 0
    total_revenue = rent_total + util_total
    total_expenses = expenses['amount'].sum() if not expenses.empty else 0
    net_profit = total_revenue - total_expenses
    active_units = tenants[tenants['status'] != 'Checked-out']['unit_room'].nunique() if not tenants.empty else 0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Rent Collected", f"₱{rent_total:,.2f}")
    m2.metric("Utility Collected", f"₱{util_total:,.2f}")
    m3.metric("Total Expenses", f"₱{total_expenses:,.2f}")
    m4.metric("Net Profit", f"₱{net_profit:,.2f}", delta=float(net_profit))

    st.divider()
    
    if tenants.empty and tenant_payments.empty and expenses.empty:
        st.info("Database is empty. Please enter data in the 'Data Entry' tab.")
    else:
        st.subheader("📈 Financial Performance Trend")
        if not tenant_payments.empty or not expenses.empty:
            rev_ts = tenant_payments.copy()
            rev_ts['date'] = pd.to_datetime(rev_ts['payment_date']).dt.to_period('M').dt.to_timestamp()
            rev_monthly = rev_ts.groupby('date')['amount'].sum().reset_index().rename(columns={'amount': 'Revenue'})
            exp_ts = expenses.copy()
            exp_ts['date'] = pd.to_datetime(exp_ts['bill_date']).dt.to_period('M').dt.to_timestamp()
            exp_monthly = exp_ts.groupby('date')['amount'].sum().reset_index().rename(columns={'amount': 'Expenses'})
            performance_df = pd.merge(rev_monthly, exp_monthly, on='date', how='outer').fillna(0).sort_values('date')
            
            fig_perf = px.line(performance_df, x='date', y=['Revenue', 'Expenses'], 
                               color_discrete_map={'Revenue': '#507d00', 'Expenses': '#f44336'},
                               markers=True)
            st.plotly_chart(fig_perf, use_container_width=True, config=CHART_CONFIG)
        
        st.divider()
        col_rev, col_exp_pie = st.columns([1, 1])
        with col_rev:
            st.subheader("📊 Revenue Composition")
            rev_data = pd.DataFrame({'Source': ['Base Rent', 'Utilities'], 'Amount': [rent_total, util_total]})
            fig_rev = px.bar(rev_data, x='Source', y='Amount', color='Source', color_discrete_map={'Base Rent': '#507d00', 'Utilities': '#ffc107'})
            st.plotly_chart(fig_rev, use_container_width=True, config=CHART_CONFIG)
            
        with col_exp_pie:
            st.subheader("🥧 Expense Breakdown")
            if not expenses.empty:
                fig_pie = px.pie(expenses, values='amount', names='category', hole=0.4, color_discrete_sequence=px.colors.qualitative.Safe)
                st.plotly_chart(fig_pie, use_container_width=True, config=CHART_CONFIG)

# --- DATA ENTRY ---
elif menu == "Data Entry":
    tab_exp, tab_rent, tab_util = st.tabs(["⚡ Main Bills", "🏠 Rent Collection", "🔢 Meter Payments"])
    active_residents = tenants[tenants['status'] != 'Checked-out'] if not tenants.empty else pd.DataFrame()
    guest_names = active_residents['guest_name'].unique().tolist() if not active_residents.empty else []

    with tab_exp:
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
                        st.cache_data.clear()
                        st.rerun()

    with tab_rent:
        selected_guest = st.selectbox("Select Tenant Name", ["-- Select Guest --"] + guest_names, key="rent_name_select")
        auto_unit = str(active_residents[active_residents['guest_name'] == selected_guest].iloc[-1]['unit_room']) if selected_guest != "-- Select Guest --" else ""
        with st.form("rent_form", clear_on_submit=True):
            unit = st.text_input("Unit/Room", value=auto_unit, key=f"rent_unit_{selected_guest}")
            r_amount = st.number_input("Monthly Rent Amount (₱)", min_value=0.0, step=500.0)
            r_date = st.date_input("Payment Date")
            if st.form_submit_button("Save Rent Payment"):
                if r_amount > 0 and selected_guest != "-- Select Guest --":
                    conn = get_connection()
                    if conn:
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO tenant_payments (guest_name, unit_room, payment_type, sub_category, amount, payment_date) VALUES (%s, %s, %s, %s, %s, %s)", 
                                     (selected_guest, unit, 'Rent', 'Monthly Rent', r_amount, r_date))
                        conn.commit(); conn.close()
                        st.success("Rent recorded.")
                        st.cache_data.clear()
                        st.rerun()

    with tab_util:
        selected_guest_u = st.selectbox("Select Tenant Name", ["-- Select Guest --"] + guest_names, key="util_name_select")
        auto_unit_u = str(active_residents[active_residents['guest_name'] == selected_guest_u].iloc[-1]['unit_room']) if selected_guest_u != "-- Select Guest --" else ""
        with st.form("util_payment_form", clear_on_submit=True):
            unit_u = st.text_input("Unit/Room", value=auto_unit_u, key=f"util_unit_{selected_guest_u}")
            p_col1, p_col2 = st.columns(2)
            p_type = p_col1.selectbox("Utility Type", ["Electricity (Sub-meter)", "Water (Sub-meter)", "Internet", "Maintenance Fee"])
            p_amount = p_col2.number_input("Amount Collected (₱)", min_value=0.0, step=50.0)
            p_date = st.date_input("Collection Date")
            if st.form_submit_button("Save Utility Payment"):
                if p_amount > 0 and selected_guest_u != "-- Select Guest --":
                    conn = get_connection()
                    if conn:
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO tenant_payments (guest_name, unit_room, payment_type, sub_category, amount, payment_date) VALUES (%s, %s, %s, %s, %s, %s)", 
                                     (selected_guest_u, unit_u, 'Utility', p_type, p_amount, p_date))
                        conn.commit(); conn.close()
                        st.success("Utility payment saved.")
                        st.cache_data.clear()
                        st.rerun()

# --- REPORTS & EXPORT ---
elif menu == "Reports & Export":
    st.subheader("📥 Data & Visual Reports")
    
    st.markdown("""
        <div style="background-color: #f0f7f0; padding: 20px; border-radius: 12px; border: 1px solid #cce2cc;">
            <h4 style="color: #507d00; margin-top: 0;">📸 How to Download Graphs</h4>
            <p style="font-size: 14px; color: #555;">Hover your mouse over any graph. A menu will appear in the top-right corner. Click the <b>Camera Icon</b> to save the graph as a PNG image for your records.</p>
        </div>
    """, unsafe_allow_html=True)
    
    st.divider()
    
    if not tenant_payments.empty or not expenses.empty:
        # Master Ledger Export
        df_in = tenant_payments[['payment_date', 'guest_name', 'sub_category', 'amount']].copy()
        df_in['Type'] = 'Revenue (In)'
        df_in.columns = ['Date', 'Entity', 'Category', 'Amount', 'Type']
        df_out = expenses[['bill_date', 'category', 'amount']].copy()
        df_out['Type'] = 'Expense (Out)'
        df_out['Entity'] = 'Main Bill'
        df_out.columns = ['Date', 'Category', 'Amount', 'Type', 'Entity']
        master_df = pd.concat([df_in, df_out]).sort_values('Date', ascending=False)
        
        csv_master = master_df.to_csv(index=False).encode('utf-8')
        st.download_button("✨ DOWNLOAD UNIFIED MASTER LEDGER (CSV)", data=csv_master, file_name=f"amore_master_ledger_{datetime.now().strftime('%Y%m%d')}.csv", mime='text/csv', use_container_width=True)
        st.dataframe(master_df.head(10), use_container_width=True, hide_index=True)

        st.divider()

        # Re-adding individual downloads
        col_exp1, col_exp2 = st.columns(2)
        with col_exp1:
            st.write("#### 💰 Tenant Payments (Individual)")
            csv_payments = tenant_payments.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download Payment Records",
                data=csv_payments,
                file_name=f"amore_tenant_payments_{datetime.now().strftime('%Y%m%d')}.csv",
                mime='text/csv',
                use_container_width=True
            )
            
        with col_exp2:
            st.write("#### 💸 Main Bills (Individual)")
            csv_expenses = expenses.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download Expense Records",
                data=csv_expenses,
                file_name=f"amore_expenses_{datetime.now().strftime('%Y%m%d')}.csv",
                mime='text/csv',
                use_container_width=True
            )
    else:
        st.info("No data available to export.")

# --- UTILITY RECONCILIATION ---
elif menu == "Utility Reconciliation":
    st.subheader("⚖️ Reconciliation")
    u_type = st.selectbox("Select Utility", ["Electricity", "Water", "Internet"])
    paid = expenses[expenses['category'] == u_type]['amount'].sum() if not expenses.empty else 0
    collected = tenant_payments[(tenant_payments['payment_type'] == 'Utility') & (tenant_payments['sub_category'].str.contains(u_type, case=False))]['amount'].sum() if not tenant_payments.empty else 0
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Main Bill", f"₱{paid:,.2f}")
    c2.metric("Sub-meters", f"₱{collected:,.2f}")
    gap = collected - paid
    c3.metric("Gap", f"₱{gap:,.2f}", delta=float(gap), delta_color="normal" if gap >= 0 else "inverse")
    if paid > 0:
        st.progress(min(collected / paid, 1.0))

# --- SETTINGS ---
elif menu == "Sync Settings":
    st.subheader("⚙️ Settings")
    if st.button("Refresh Data"):
        st.cache_data.clear()
        st.rerun()

st.caption("Amore Financial Cloud v2.4 | All Export Options Restored")