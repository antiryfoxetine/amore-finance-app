import streamlit as st
import mysql.connector
import pandas as pd
import plotly.express as px
from datetime import datetime, date, timedelta
import os

# --- PAGE CONFIG ---
st.set_page_config(page_title="Amore Financial Cloud", layout="wide", page_icon="🏠")

# --- BRANDING & LOGO ---
# Fixed Raw URL based on your GitHub repo: antiryfoxetine/amore-finance-app
LOGO_URL = "https://raw.githubusercontent.com/antiryfoxetine/amore-finance-app/main/logo.png" 

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
    if not DB_CONFIG:
        return None
    try:
        return mysql.connector.connect(**DB_CONFIG, connection_timeout=10)
    except Exception as e:
        st.sidebar.error(f"Connection Error: {e}")
        return None

# --- INITIALIZE DATABASE TABLES ---
def init_db():
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor()
            # Table for building expenses
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS expenses (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    category VARCHAR(255),
                    amount DECIMAL(10,2),
                    bill_date DATE,
                    description TEXT
                )
            """)
            # Table for tenant payments
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
            # Create a dummy bookings table if it doesn't exist yet (to prevent fetch errors)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bookings (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    guest_name VARCHAR(255),
                    unit_room VARCHAR(50),
                    status VARCHAR(50)
                )
            """)
            conn.commit()
        except Exception as e:
            st.error(f"Database Table Error: {e}")
        finally:
            conn.close()

init_db()

# --- LOGIN LOGIC ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    col_l1, col_l2, col_l3 = st.columns([1, 1, 1])
    with col_l2:
        st.markdown("<div style='text-align: center;'>", unsafe_allow_html=True)
        try:
            st.image(LOGO_URL, width=150)
        except:
            st.markdown("<h1>🏠</h1>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown("""
            <div style="text-align: center; padding-bottom: 20px;">
                <h1 style="color: #507d00; font-family: 'Segoe UI', sans-serif; margin-top: 10px;">AMORE FINANCE</h1>
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
    .stMetric { background-color: white; padding: 15px; border-radius: 12px; border: 1px solid #f0f2f6; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    [data-testid="stSidebar"] { background-color: #f8fafc; }
    </style>
    <div class="main-header">
        <h1 style="margin:0;">AMORE FINANCIAL TRACKER</h1>
    </div>
    """, unsafe_allow_html=True)

# --- DATA FETCHING (CACHED) ---
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
        except Exception as e:
            if conn: conn.close()
            # If tables are missing, we still return empty DFs but don't warn about connection
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

tenants, expenses_raw, tenant_payments_raw = fetch_data()

# --- SIDEBAR & GLOBAL FILTERS ---
with st.sidebar:
    try:
        st.image(LOGO_URL, width=150)
    except:
        st.markdown("Logo error")
        
    st.write(f"User: **Business Admin**")
    
    st.divider()
    st.subheader("📅 Global Date Filter")
    today = date.today()
    # 1 year default range
    one_year_ago = today - timedelta(days=365)
    date_range = st.date_input("Filter Period", [one_year_ago, today])
    
    st.divider()
    menu = st.radio("Navigate", ["Dashboard", "Data Entry", "Utility Reconciliation", "Reports & Export", "Sync Settings"])
    
    if st.button("Logout", use_container_width=True):
        st.session_state.logged_in = False
        st.rerun()

# Apply Global Date Filters
expenses = expenses_raw.copy()
tenant_payments = tenant_payments_raw.copy()

if len(date_range) == 2:
    start_date, end_date = date_range
    if not tenant_payments.empty:
        tenant_payments['payment_date'] = pd.to_datetime(tenant_payments['payment_date']).dt.date
        tenant_payments = tenant_payments[(tenant_payments['payment_date'] >= start_date) & (tenant_payments['payment_date'] <= end_date)]
    if not expenses.empty:
        expenses['bill_date'] = pd.to_datetime(expenses['bill_date']).dt.date
        expenses = expenses[(expenses['bill_date'] >= start_date) & (expenses['bill_date'] <= end_date)]

# Chart Config for Downloads
CHART_CONFIG = {
    'displayModeBar': True,
    'toImageButtonOptions': {'format': 'png', 'filename': 'amore_report', 'height': 600, 'width': 1000, 'scale': 2}
}

# --- DASHBOARD ---
if menu == "Dashboard":
    # Only show warning if we can't get a connection at all
    conn_check = get_connection()
    if not conn_check:
        st.warning("⚠️ Database connection failed. Please check your Aiven IP Allowlist and Streamlit Secrets.")
    elif conn_check:
        conn_check.close()
    
    rent_total = tenant_payments[tenant_payments['payment_type'] == 'Rent']['amount'].sum() if not tenant_payments.empty else 0
    util_total = tenant_payments[tenant_payments['payment_type'] == 'Utility']['amount'].sum() if not tenant_payments.empty else 0
    total_expenses = expenses['amount'].sum() if not expenses.empty else 0
    net_profit = (rent_total + util_total) - total_expenses
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Rent Collected", f"₱{rent_total:,.2f}")
    m2.metric("Utility Collected", f"₱{util_total:,.2f}")
    m3.metric("Total Expenses", f"₱{total_expenses:,.2f}")
    m4.metric("Net Profit", f"₱{net_profit:,.2f}", delta=float(net_profit))

    st.divider()
    
    if tenant_payments.empty and expenses.empty:
        st.info("No financial data found for the selected dates. Add entries in 'Data Entry' to see results.")
    else:
        st.subheader("📈 Financial Performance Trend")
        if not tenant_payments.empty or not expenses.empty:
            rev_ts = tenant_payments.copy()
            rev_ts['date'] = pd.to_datetime(rev_ts['payment_date'])
            rev_daily = rev_ts.groupby('date')['amount'].sum().reset_index().rename(columns={'amount': 'Revenue'})
            exp_ts = expenses.copy()
            exp_ts['date'] = pd.to_datetime(exp_ts['bill_date'])
            exp_daily = exp_ts.groupby('date')['amount'].sum().reset_index().rename(columns={'amount': 'Expenses'})
            perf_df = pd.merge(rev_daily, exp_daily, on='date', how='outer').fillna(0).sort_values('date')
            fig_perf = px.line(perf_df, x='date', y=['Revenue', 'Expenses'], 
                               color_discrete_map={'Revenue': '#507d00', 'Expenses': '#f44336'}, markers=True)
            st.plotly_chart(fig_perf, use_container_width=True, config=CHART_CONFIG)

        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("📊 Revenue Composition")
            fig_rev = px.bar(pd.DataFrame({'Source': ['Rent', 'Utilities'], 'Amount': [rent_total, util_total]}), 
                             x='Source', y='Amount', color='Source', color_discrete_map={'Rent': '#507d00', 'Utilities': '#ffc107'})
            st.plotly_chart(fig_rev, use_container_width=True, config=CHART_CONFIG)
        with col_b:
            st.subheader("🥧 Expense Breakdown")
            if not expenses.empty:
                fig_pie = px.pie(expenses, values='amount', names='category', hole=0.4, color_discrete_sequence=px.colors.qualitative.Safe)
                st.plotly_chart(fig_pie, use_container_width=True, config=CHART_CONFIG)

# --- DATA ENTRY ---
elif menu == "Data Entry":
    tab_exp, tab_rent, tab_util = st.tabs(["⚡ Main Bills", "🏠 Rent Collection", "🔢 Meter Payments"])
    
    # Logic to handle missing residents
    active_residents = tenants[tenants['status'] != 'Checked-out'] if not tenants.empty else pd.DataFrame()
    guest_names = active_residents['guest_name'].unique().tolist() if not active_residents.empty else []

    with tab_exp:
        with st.form("expense_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            cat = c1.selectbox("Type", ["Electricity", "Water", "Internet", "Maintenance", "Staff Salary"])
            amt = c2.number_input("Amount (₱)", min_value=0.0)
            dt = st.date_input("Date")
            if st.form_submit_button("Save Bill"):
                if amt > 0:
                    conn = get_connection()
                    if conn:
                        cur = conn.cursor()
                        cur.execute("INSERT INTO expenses (category, amount, bill_date) VALUES (%s, %s, %s)", (cat, amt, dt))
                        conn.commit(); conn.close(); st.success("Bill saved!"); st.cache_data.clear(); st.rerun()
                    else: st.error("Database connection failed.")

    with tab_rent:
        if not guest_names:
            st.warning("No active guests found in the 'bookings' table. Please add guests to your booking app first.")
        sel_guest = st.selectbox("Guest", ["-- Select Guest --"] + guest_names, key="r_sel")
        unit_lookup = str(active_residents[active_residents['guest_name'] == sel_guest].iloc[-1]['unit_room']) if sel_guest != "-- Select Guest --" else ""
        with st.form("rent_form", clear_on_submit=True):
            u = st.text_input("Unit", value=unit_lookup, key=f"u_r_{sel_guest}")
            amt = st.number_input("Rent (₱)", min_value=0.0)
            dt = st.date_input("Date")
            if st.form_submit_button("Save Rent"):
                if amt > 0 and sel_guest != "-- Select Guest --":
                    conn = get_connection()
                    if conn:
                        cur = conn.cursor()
                        cur.execute("INSERT INTO tenant_payments (guest_name, unit_room, payment_type, sub_category, amount, payment_date) VALUES (%s, %s, %s, %s, %s, %s)", 
                                     (sel_guest, u, 'Rent', 'Monthly Rent', amt, dt))
                        conn.commit(); conn.close(); st.success("Rent recorded!"); st.cache_data.clear(); st.rerun()

    with tab_util:
        sel_guest_u = st.selectbox("Guest", ["-- Select Guest --"] + guest_names, key="u_sel")
        unit_lookup_u = str(active_residents[active_residents['guest_name'] == sel_guest_u].iloc[-1]['unit_room']) if sel_guest_u != "-- Select Guest --" else ""
        with st.form("util_form", clear_on_submit=True):
            u_u = st.text_input("Unit", value=unit_lookup_u, key=f"u_u_{sel_guest_u}")
            p_cat = st.selectbox("Utility", ["Electricity (Sub-meter)", "Water (Sub-meter)", "Internet", "Maintenance Fee"])
            amt = st.number_input("Amount (₱)", min_value=0.0)
            dt = st.date_input("Date")
            if st.form_submit_button("Save Utility"):
                if amt > 0 and sel_guest_u != "-- Select Guest --":
                    conn = get_connection()
                    if conn:
                        cur = conn.cursor()
                        cur.execute("INSERT INTO tenant_payments (guest_name, unit_room, payment_type, sub_category, amount, payment_date) VALUES (%s, %s, %s, %s, %s, %s)", 
                                     (sel_guest_u, u_u, 'Utility', p_cat, amt, dt))
                        conn.commit(); conn.close(); st.success("Utility saved!"); st.cache_data.clear(); st.rerun()

    st.divider()
    st.subheader("🗑️ Record Management (Admin)")
    col_del1, col_del2 = st.columns(2)
    with col_del1:
        st.write("#### Recent Payments")
        if not tenant_payments.empty:
            for idx, row in tenant_payments.tail(5).iterrows():
                if st.button(f"🗑️ {row['guest_name']} (₱{row['amount']})", key=f"del_p_{row['id']}", use_container_width=True):
                    conn = get_connection()
                    if conn:
                        cur = conn.cursor()
                        cur.execute("DELETE FROM tenant_payments WHERE id=%s", (row['id'],))
                        conn.commit(); conn.close(); st.cache_data.clear(); st.rerun()
    with col_del2:
        st.write("#### Recent Bills")
        if not expenses.empty:
            for idx, row in expenses.tail(5).iterrows():
                if st.button(f"🗑️ {row['category']} (₱{row['amount']})", key=f"del_e_{row['id']}", use_container_width=True):
                    conn = get_connection()
                    if conn:
                        cur = conn.cursor()
                        cur.execute("DELETE FROM expenses WHERE id=%s", (row['id'],))
                        conn.commit(); conn.close(); st.cache_data.clear(); st.rerun()

# --- REPORTS & EXPORT ---
elif menu == "Reports & Export":
    st.subheader("📥 Financial Reports")
    
    if not tenant_payments.empty or not expenses.empty:
        # P&L Calculation
        p_rent = tenant_payments[tenant_payments['payment_type'] == 'Rent']['amount'].sum()
        p_util = tenant_payments[tenant_payments['payment_type'] == 'Utility']['amount'].sum()
        total_income = p_rent + p_util
        exp_sum = expenses.groupby('category')['amount'].sum().reset_index()
        total_exp = exp_sum['amount'].sum()
        
        st.write("#### 📄 Profit & Loss Summary")
        pnl_df = pd.DataFrame([
            {'Item': 'Rental Income', 'Amount': p_rent},
            {'Item': 'Utility Recovery', 'Amount': p_util},
            {'Item': 'TOTAL REVENUE', 'Amount': total_income},
            {'Item': 'TOTAL EXPENSES', 'Amount': -total_exp},
            {'Item': 'NET PROFIT', 'Amount': total_income - total_exp}
        ])
        st.table(pnl_df)
        
        st.divider()
        st.write("#### ✨ Master Ledger Download")
        df_in = tenant_payments[['payment_date', 'guest_name', 'sub_category', 'amount']].copy()
        df_in['Type'] = 'INCOME'
        df_out = expenses[['bill_date', 'category', 'amount']].copy()
        df_out['Type'] = 'EXPENSE'
        df_out.columns = ['Date', 'Category', 'Amount', 'Type']
        df_in.columns = ['Date', 'Entity', 'Category', 'Amount', 'Type']
        master = pd.concat([df_in, df_out]).sort_values('Date', ascending=False)
        
        st.download_button("💾 DOWNLOAD MASTER REPORT (CSV)", master.to_csv(index=False).encode('utf-8'), 
                           f"amore_master_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv", use_container_width=True)
    else:
        st.info("No records to export.")

# --- UTILITY RECONCILIATION ---
elif menu == "Utility Reconciliation":
    u_type = st.selectbox("Utility", ["Electricity", "Water", "Internet"])
    p = expenses[expenses['category'] == u_type]['amount'].sum() if not expenses.empty else 0
    c = tenant_payments[(tenant_payments['payment_type'] == 'Utility') & (tenant_payments['sub_category'].str.contains(u_type, case=False))]['amount'].sum() if not tenant_payments.empty else 0
    c1, c2, c3 = st.columns(3)
    c1.metric("Main Bill", f"₱{p:,.2f}")
    c2.metric("Sub-meters", f"₱{c:,.2f}")
    c3.metric("Gap", f"₱{c-p:,.2f}", delta=float(c-p))
    if p > 0: st.progress(min(c/p, 1.0))

# --- SETTINGS ---
elif menu == "Sync Settings":
    if st.button("Refresh Cache"):
        st.cache_data.clear(); st.rerun()
    st.info("Database: Aiven MySQL Online")

st.caption("Amore Financial Cloud v2.8 | Logo Fixed & Connection Safeguards Enabled")