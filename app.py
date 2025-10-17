import streamlit as st
import pandas as pd
import glob
import os

st.set_page_config(page_title="Sales Dashboard", layout="wide")
st.title("📊 Multi-Source Sales Dashboard")

# --- Dropdown to choose dataset ---
data_source = st.sidebar.selectbox("Select Data Source", ["POS", "Online"])

# Define folders for each data type
folder_paths = {
    "POS": "sales_data",
    "Online": "online_Data
}

folder_path = folder_paths[data_source]

# Get CSV files
files = glob.glob(os.path.join(folder_path, "*.csv"))

if not files:
    st.warning(f"No files found in folder: `{folder_path}`")
else:
    # --- Read and merge all files safely ---
    df_list = []
    for f in files:
        try:
            data = pd.read_csv(f, low_memory=False)
            df_list.append(data)
        except Exception as e:
            st.error(f"❌ Error reading {f}: {e}")

    if not df_list:
        st.error("No valid data files could be read.")
        st.stop()

    df = pd.concat(df_list, ignore_index=True)

    # --- Clean column names ---
    df.columns = df.columns.str.strip()
    df = df.loc[:, ~df.columns.duplicated()]

    # --- Identify columns dynamically ---
    possible_date_cols = [col for col in df.columns if "date" in col.lower()]
    possible_amount_cols = [col for col in df.columns if "amount" in col.lower() or "total" in col.lower()]
    possible_qty_cols = [col for col in df.columns if "qty" in col.lower() or "quantity" in col.lower()]

    # --- Normalize key columns if found ---
    if possible_date_cols:
        df.rename(columns={possible_date_cols[0]: "Date"}, inplace=True)
    if possible_amount_cols:
        df.rename(columns={possible_amount_cols[0]: "Amount"}, inplace=True)
    if possible_qty_cols:
        df.rename(columns={possible_qty_cols[0]: "Quantity Ordered"}, inplace=True)

    # --- Convert data types safely ---
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce", dayfirst=True)
    if "Amount" in df.columns:
        df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
    if "Quantity Ordered" in df.columns:
        df["Quantity Ordered"] = pd.to_numeric(df["Quantity Ordered"], errors="coerce")

    # --- Sidebar Filters ---
    st.sidebar.header("🔍 Filters")

    store_filter = None
    if "Store" in df.columns:
        store_filter = st.sidebar.multiselect("Select Store(s)", sorted(df["Store"].dropna().unique()))

    date_range = st.sidebar.date_input("Select Date Range", [])

    filtered_df = df.copy()
    if store_filter:
        filtered_df = filtered_df[filtered_df["Store"].isin(store_filter)]

    if len(date_range) == 2:
        start_date, end_date = date_range
        filtered_df = filtered_df[
            (filtered_df["Date"] >= pd.to_datetime(start_date))
            & (filtered_df["Date"] <= pd.to_datetime(end_date))
        ]

    # --- KPIs ---
    total_sales = filtered_df["Amount"].sum() if "Amount" in filtered_df.columns else 0
    total_qty = filtered_df["Quantity Ordered"].sum() if "Quantity Ordered" in filtered_df.columns else 0
    total_records = len(filtered_df)

    c1, c2, c3 = st.columns(3)
    c1.metric("💰 Total Sales", f"₹{total_sales:,.0f}")
    c2.metric("📦 Total Quantity", f"{total_qty:,.0f}")
    c3.metric("🧾 Total Records", f"{total_records:,}")

    st.divider()

    # --- 1️⃣ Daily Sales Trend ---
    if "Date" in filtered_df.columns and "Amount" in filtered_df.columns:
        st.subheader("📅 Daily Sales Trend")
        daily_sales = filtered_df.groupby("Date")["Amount"].sum().reset_index()
        st.line_chart(daily_sales, x="Date", y="Amount", width="stretch")

    # --- 2️⃣ Store-wise Sales ---
    if "Store" in filtered_df.columns and "Amount" in filtered_df.columns:
        st.subheader("🏬 Store-wise Sales")
        store_sales = (
            filtered_df.groupby("Store")["Amount"].sum().reset_index().sort_values(by="Amount", ascending=False)
        )
        st.bar_chart(store_sales.set_index("Store"), width="stretch")

    # --- 3️⃣ Product Performance ---
    if "Product" in filtered_df.columns:
        # Fix for "Product not 1-dimensional" issue
        filtered_df = filtered_df.loc[:, ~filtered_df.columns.duplicated()]
        if isinstance(filtered_df["Product"], pd.DataFrame):
            filtered_df["Product"] = filtered_df["Product"].iloc[:, 0]
        filtered_df["Product"] = filtered_df["Product"].astype(str)

        if all(col in filtered_df.columns for col in ["Quantity Ordered", "Amount"]):
            st.subheader("🧾 Product Performance")
            product_summary = (
                filtered_df.groupby("Product")[["Quantity Ordered", "Amount"]]
                .sum()
                .reset_index()
                .sort_values(by="Amount", ascending=False)
            )
            st.dataframe(product_summary, width="stretch")

    # --- 4️⃣ Size-wise Quantity ---
    if "Size" in filtered_df.columns and "Quantity Ordered" in filtered_df.columns:
        st.subheader("👟 Size-wise Quantity Ordered")
        size_summary = (
            filtered_df.groupby("Size")["Quantity Ordered"]
            .sum()
            .reset_index()
            .sort_values(by="Quantity Ordered", ascending=False)
        )
        st.bar_chart(size_summary.set_index("Size"), width="stretch")

    st.success(f"✅ Loaded {len(files)} files successfully from `{data_source}` folder.")
