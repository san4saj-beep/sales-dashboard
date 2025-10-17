import streamlit as st
import pandas as pd
import glob
import os

st.set_page_config(page_title="Sales Dashboard", layout="wide")
st.title("📊 Multi-Source Sales Dashboard")

# Folder paths
data_sources = {
    "POS Sales": "sales_data",
    "Online Sales (Magento)": "online_data"
}

# Sidebar dropdown
source_choice = st.sidebar.selectbox("Select Data Source", list(data_sources.keys()))
folder_path = data_sources[source_choice]

# Load CSV files from the selected folder
files = glob.glob(os.path.join(folder_path, "*.csv"))

if not files:
    st.warning(f"No CSV files found in folder: {folder_path}")
    st.stop()

# Combine all CSVs from the folder
df_list = []
for f in files:
    try:
        data = pd.read_csv(f)
        df_list.append(data)
    except Exception as e:
        st.error(f"Error reading {f}: {e}")

df = pd.concat(df_list, ignore_index=True)

# --- Normalize column names ---
df.columns = [col.strip().title() for col in df.columns]

# Define flexible column name mapping for POS and Online
col_map = {
    'Sku': 'Product',
    'Product Name': 'Product',
    'Order Qty': 'Quantity Ordered',
    'Quantity': 'Quantity Ordered',
    'Total': 'Amount',
    'Sales': 'Amount',
    'Store Name': 'Store'
}
df.rename(columns={k: v for k, v in col_map.items() if k in df.columns}, inplace=True)

# --- Handle missing columns gracefully ---
for col in ['Date', 'Product', 'Quantity Ordered', 'Amount']:
    if col not in df.columns:
        df[col] = None

if 'Store' not in df.columns:
    df['Store'] = source_choice  # Label as "POS" or "Online"

# --- Clean and convert data types ---
df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
df['Quantity Ordered'] = pd.to_numeric(df['Quantity Ordered'], errors='coerce')
df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce')

# --- Sidebar Filters ---
st.sidebar.header("🔍 Filters")
if 'Store' in df.columns:
    store_filter = st.sidebar.multiselect("Select Store(s)", sorted(df['Store'].dropna().unique()))
else:
    store_filter = []

date_range = st.sidebar.date_input("Select Date Range", [])

filtered_df = df.copy()
if store_filter:
    filtered_df = filtered_df[filtered_df['Store'].isin(store_filter)]
if len(date_range) == 2:
    start_date, end_date = date_range
    filtered_df = filtered_df[
        (filtered_df['Date'] >= pd.to_datetime(start_date)) &
        (filtered_df['Date'] <= pd.to_datetime(end_date))
    ]

# --- KPIs ---
total_sales = filtered_df['Amount'].sum(skipna=True)
total_qty = filtered_df['Quantity Ordered'].sum(skipna=True)
total_records = len(filtered_df)

c1, c2, c3 = st.columns(3)
c1.metric("💰 Total Sales", f"₹{total_sales:,.0f}")
c2.metric("📦 Total Quantity", f"{total_qty:,.0f}")
c3.metric("🧾 Total Records", f"{total_records:,}")

st.divider()

# --- Charts ---
if not filtered_df.empty and 'Date' in filtered_df.columns:
    st.subheader("📅 Daily Sales Trend")
    daily_sales = filtered_df.groupby('Date')['Amount'].sum().reset_index()
    st.line_chart(daily_sales, x='Date', y='Amount', width='stretch')

if 'Store' in filtered_df.columns:
    st.subheader("🏬 Store-wise Sales")
    store_sales = filtered_df.groupby('Store')['Amount'].sum().reset_index().sort_values(by='Amount', ascending=False)
    st.bar_chart(store_sales.set_index('Store'))

if 'Product' in filtered_df.columns:
    st.subheader("🧾 Product Performance")

    # Handle multi-dimensional or duplicated 'Product' columns safely
    if isinstance(filtered_df['Product'], pd.DataFrame):
        filtered_df['Product'] = filtered_df['Product'].iloc[:, 0]  # pick first column
    elif filtered_df['Product'].apply(lambda x: isinstance(x, (list, dict))).any():
        filtered_df['Product'] = filtered_df['Product'].astype(str)

    try:
        product_summary = (
            filtered_df.groupby('Product', dropna=False)[['Quantity Ordered', 'Amount']]
            .sum()
            .reset_index()
            .sort_values(by='Amount', ascending=False)
        )
        st.dataframe(product_summary, use_container_width=True)
    except Exception as e:
        st.error(f"Could not generate product summary: {e}")
else:
    st.info("No 'Product' column found in this dataset.")
