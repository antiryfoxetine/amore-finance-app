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
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { background-color: #f8fafc; border-radius: 8px 8px 0 0; padding: 10px 20px; }
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
    menu = st.radio("Navigate", ["Dashboard", "Data Entry", "Utility Reconciliation", "Reports & Export", "Sync Settings"])
    if st.button("Logout", use_container_width=True):
        st.session_state.logged_in = False
        st.rerun()

# --- DASHBOARD ---
if menu == "Dashboard":
    # Revenue calculations
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
        st.info("No data yet. Head over to the 'Data Entry' tab to get started.")
    else:
        # Financial Performance Graph (Time Series)
        st.subheader("📈 Financial Performance Trend")
        
        # Prepare data for time series
        if not tenant_payments.empty or not expenses.empty:
            rev_ts = tenant_payments.copy()
            rev_ts['date'] = pd.to_datetime(rev_ts['payment_date']).dt.to_period('M').dt.to_timestamp()
            rev_monthly = rev_ts.groupby('date')['amount'].sum().reset_index().rename(columns={'amount': 'Revenue'})
            
            exp_ts = expenses.copy()
            exp_ts['date'] = pd.to_datetime(exp_ts['bill_date']).dt.to_period('M').dt.to_timestamp()
            exp_monthly = exp_ts.groupby('date')['amount'].sum().reset_index().rename(columns={'amount': 'Expenses'})
            
            performance_df = pd.merge(rev_monthly, exp_monthly, on='date', how='outer').fillna(0)
            performance_df = performance_df.sort_values('date')
            
            fig_perf = px.line(performance_df, x='date', y=['Revenue', 'Expenses'], 
                               labels={'value': 'Amount (₱)', 'date': 'Month'},
                               color_discrete_map={'Revenue': '#507d00', 'Expenses': '#f44336'},
                               markers=True)
            fig_perf.update_layout(hovermode="x unified")
            st.plotly_chart(fig_perf, use_container_width=True)
        else:
            st.info("Not enough data to generate trend graph.")

        st.divider()

        # Top Row: Charts
        col_rev, col_exp_pie = st.columns([1, 1])
        with col_rev:
            st.subheader("📊 Revenue Composition")
            rev_data = pd.DataFrame({
                'Source': ['Base Rent', 'Utilities'],
                'Amount': [rent_total, util_total]
            })
            fig_rev = px.bar(rev_data, x='Source', y='Amount', color='Source', 
                             color_discrete_map={'Base Rent': '#507d00', 'Utilities': '#ffc107'})
            st.plotly_chart(fig_rev, use_container_width=True)
            
        with col_exp_pie:
            st.subheader("🥧 Expense Breakdown")
            if not expenses.empty:
                fig_pie = px.pie(expenses, values='amount', names='category', hole=0.4, 
                                 color_discrete_sequence=px.colors.qualitative.Safe)
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("No expenses recorded yet to show breakdown.")

        st.divider()

        # Bottom Row: Tables
        col_list, col_bill_list = st.columns([1, 1])
        with col_list:
            st.subheader("📋 Latest Tenant Payments")
            if not tenant_payments.empty:
                st.dataframe(tenant_payments[['guest_name', 'sub_category', 'amount', 'payment_date']].tail(5).sort_values('payment_date', ascending=False), 
                             use_container_width=True, hide_index=True)
            else:
                st.caption("Waiting for payment records...")

        with col_bill_list:
            st.subheader("💸 Recent Main Bills (Expenses)")
            if not expenses.empty:
                st.dataframe(expenses[['category', 'amount', 'bill_date']].tail(5).sort_values('bill_date', ascending=False),
                             use_container_width=True, hide_index=True)
            else:
                st.caption("Waiting for bill records...")

# --- DATA ENTRY ---
elif menu == "Data Entry":
    tab_exp, tab_rent, tab_util = st.tabs(["⚡ Main Bills (Amore Pays)", "🏠 Rent Collection", "🔢 Meter Payments (Tenants)"])
    
    # Pre-filtering for the dropdowns
    active_residents = tenants[tenants['status'] != 'Checked-out'] if not tenants.empty else pd.DataFrame()
    guest_names = active_residents['guest_name'].unique().tolist() if not active_residents.empty else []

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
                        st.success("Main bill successfully saved to cloud.")
                        st.rerun()

    with tab_rent:
        st.write("### Record Tenant Rent")
        selected_guest = st.selectbox("Select Tenant Name", ["-- Select Guest --"] + guest_names, key="rent_name_select")
        
        auto_unit = ""
        if selected_guest != "-- Select Guest --":
            match = active_residents[active_residents['guest_name'] == selected_guest]
            if not match.empty:
                auto_unit = str(match.iloc[-1]['unit_room'])

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
                        st.success(f"Rent recorded for {selected_guest}.")
                        st.rerun()
                else:
                    st.warning("Please choose a guest and enter the amount.")

    with tab_util:
        st.write("### Record Sub-meter Payments")
        selected_guest_u = st.selectbox("Select Tenant Name", ["-- Select Guest --"] + guest_names, key="util_name_select")
        
        auto_unit_u = ""
        if selected_guest_u != "-- Select Guest --":
            match_u = active_residents[active_residents['guest_name'] == selected_guest_u]
            if not match_u.empty:
                auto_unit_u = str(match_u.iloc[-1]['unit_room'])

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
                        st.success(f"Utility payment saved for {selected_guest_u}.")
                        st.rerun()
                else:
                    st.warning("Please choose a guest and enter the amount.")

    # Recent Entry Log for verification
    st.divider()
    st.subheader("📝 Recent Ledger History")
    if not tenant_payments.empty:
        st.dataframe(tenant_payments.sort_values('payment_date', ascending=False).head(10), 
                     use_container_width=True, hide_index=True)
    else:
        st.info("No payment records found.")

# --- UTILITY RECONCILIATION ---
elif menu == "Utility Reconciliation":
    st.subheader("⚖️ Master Meter vs. Individual Meter Collections")
    u_type = st.selectbox("Select Utility to Reconcile", ["Electricity", "Water", "Internet"])
    
    paid = expenses[expenses['category'] == u_type]['amount'].sum() if not expenses.empty else 0
    search_term = u_type
    collected = tenant_payments[(tenant_payments['payment_type'] == 'Utility') & (tenant_payments['sub_category'].str.contains(search_term, case=False))]['amount'].sum() if not tenant_payments.empty else 0
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Main Bill Total", f"₱{paid:,.2f}")
    c2.metric("Total from Sub-meters", f"₱{collected:,.2f}")
    
    gap = collected - paid
    delta_color = "normal" if gap >= 0 else "inverse"
    c3.metric("Profit/Loss Gap", f"₱{gap:,.2f}", delta=float(gap), delta_color=delta_color)
    
    if paid > 0:
        st.write("### Recovery Progress Bar")
        st.progress(min(collected / paid, 1.0))
        st.caption(f"You have recovered {(collected/paid)*100:.1f}% of the building's {u_type} cost.")

# --- REPORTS & EXPORT ---
elif menu == "Reports & Export":
    st.subheader("📥 Export Financial Records")
    st.write("Download your data as CSV files for offline management or accounting.")
    
    col_exp1, col_exp2 = st.columns(2)
    
    with col_exp1:
        st.write("#### 💰 Tenant Payments (Revenue)")
        if not tenant_payments.empty:
            csv_payments = tenant_payments.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download Payment Records",
                data=csv_payments,
                file_name=f"amore_tenant_payments_{datetime.now().strftime('%Y%m%d')}.csv",
                mime='text/csv',
                use_container_width=True
            )
            st.dataframe(tenant_payments.head(5), use_container_width=True)
        else:
            st.info("No payment records available to export.")
            
    with col_exp2:
        st.write("#### 💸 Main Bills (Expenses)")
        if not expenses.empty:
            csv_expenses = expenses.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download Expense Records",
                data=csv_expenses,
                file_name=f"amore_expenses_{datetime.now().strftime('%Y%m%d')}.csv",
                mime='text/csv',
                use_container_width=True
            )
            st.dataframe(expenses.head(5), use_container_width=True)
        else:
            st.info("No expense records available to export.")

# --- SETTINGS ---
elif menu == "Sync Settings":
    st.subheader("⚙️ Cloud Synchronization")
    if st.button("Manually Refresh Data"):
        st.cache_data.clear()
        st.rerun()
    st.info("The app automatically syncs with your Aiven MySQL database.")

st.caption("Amore Financial Cloud v2.0 | Integrated Reports & Export")