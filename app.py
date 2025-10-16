import streamlit as st
import pandas as pd
import glob
import os

st.set_page_config(page_title="Sales Dashboard", layout="wide")
st.title("📊 Daily Store Sales Dashboard")

# Folder where all sales CSVs are stored
folder_path = "sales_data"
files = glob.glob(os.path.join(folder_path, "*.csv"))

if not files:
    st.warning("No sales files found in the folder yet.")
else:
    # Read and merge all files
    df_list = []
    for f in files:
        try:
            data = pd.read_csv(f)
            df_list.append(data)
        except Exception as e:
            st.error(f"Error reading {f}: {e}")

    df = pd.concat(df_list, ignore_index=True)

    # Expected columns
    expected_cols = ['Date', 'Store', 'Product', 'Quantity Ordered', 'Size', 'Amount']
    missing = [col for col in expected_cols if col not in df.columns]

    if missing:
        st.error(f"Missing columns: {missing}")
    else:
        # ✅ Clean up and convert datatypes
        df['Quantity Ordered'] = pd.to_numeric(df['Quantity Ordered'], errors='coerce')
        df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce')
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')

        # Sidebar filters
        st.sidebar.header("🔍 Filters")
        store_filter = st.sidebar.multiselect("Select Store(s)", sorted(df['Store'].unique()))
        date_range = st.sidebar.date_input("Select Date Range", [])

        filtered_df = df.copy()

        # Apply filters
        if store_filter:
            filtered_df = filtered_df[filtered_df['Store'].isin(store_filter)]
        if len(date_range) == 2:
            start_date, end_date = date_range
            filtered_df = filtered_df[
                (filtered_df['Date'] >= pd.to_datetime(start_date)) &
                (filtered_df['Date'] <= pd.to_datetime(end_date))
            ]

        # KPIs
        total_sales = filtered_df['Amount'].sum()
        total_qty = filtered_df['Quantity Ordered'].sum()
        total_records = len(filtered_df)

        c1, c2, c3 = st.columns(3)
        c1.metric("💰 Total Sales", f"₹{total_sales:,.0f}")
        c2.metric("📦 Total Quantity", f"{total_qty:,.0f}")
        c3.metric("🧾 Total Records", f"{total_records:,}")

        st.divider()

        # 1️⃣ Daily Sales Trend
        st.subheader("📅 Daily Sales Trend")
        daily_sales = filtered_df.groupby('Date')['Amount'].sum().reset_index()
        st.line_chart(daily_sales, x='Date', y='Amount', use_container_width=True)

        # 2️⃣ Store-wise Sales
        st.subheader("🏬 Store-wise Sales")
        store_sales = (
            filtered_df.groupby('Store')['Amount']
            .sum()
            .reset_index()
            .sort_values(by='Amount', ascending=False)
        )
        st.bar_chart(store_sales.set_index('Store'))

        # 3️⃣ Product + Size Performance
        st.subheader("🧾 Product & Size Performance")
        product_summary = (
            filtered_df.groupby(['Product', 'Size'])[['Quantity Ordered', 'Amount']]
            .sum()
            .reset_index()
            .sort_values(by='Amount', ascending=False)
        )
        st.dataframe(product_summary, use_container_width=True)

        st.success(f"✅ Loaded {len(files)} files successfully.")
