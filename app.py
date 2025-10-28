import streamlit as st
import pandas as pd
import os

# ---------------------------------------------------------------
# Page setup
st.set_page_config(page_title="Sales Dashboard", layout="wide")
st.title("📊 Unified Sales Dashboard")

# ---------------------------------------------------------------
# Folder paths
data_folders = {
    "POS": "sales_data",
    "Online": "online_data",
    "B2B": "B2B"
}

# Sidebar selector
selected_source = st.sidebar.selectbox("Select Data Source", list(data_folders.keys()))
folder_path = data_folders[selected_source]

if not os.path.exists(folder_path):
    st.error(f"❌ Folder '{folder_path}' not found.")
    st.stop()


# ---------------------------------------------------------------
# Function to load POS / Online CSV data
def load_csv_data(folder):
    all_data = []

    for file in os.listdir(folder):
        if file.endswith(".csv"):
            path = os.path.join(folder, file)
            df = pd.read_csv(path)
            df.columns = df.columns.astype(str).str.strip().str.title()
            df = df.loc[:, ~df.columns.duplicated()]

            # Convert data types
            if "Date" in df.columns:
                df["Date"] = pd.to_datetime(df["Date"], errors="coerce", dayfirst=True)
            if "Amount" in df.columns:
                df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
            if "Quantity Ordered" in df.columns:
                df["Quantity Ordered"] = pd.to_numeric(df["Quantity Ordered"], errors="coerce")

            all_data.append(df)

    if all_data:
        return pd.concat(all_data, ignore_index=True)
    else:
        st.warning(f"No CSV files found in {folder}")
        return pd.DataFrame()


# ---------------------------------------------------------------
# Function to load B2B Excel data
def load_b2b_data(folder):
    all_data = []

    for file in os.listdir(folder):
        if not file.endswith((".xlsx", ".xls")):
            continue

        file_path = os.path.join(folder, file)
        try:
            df = pd.read_excel(file_path)
        except Exception:
            continue

        df.columns = df.columns.astype(str).str.strip()
        df["Date"] = pd.to_datetime(df.get("Date"), errors="coerce", dayfirst=True)
        df["Voucher No."] = df["Voucher No."].ffill()
        df["Particulars"] = df["Particulars"].ffill()
        df["Value"] = pd.to_numeric(df.get("Value"), errors="coerce")

        # Clean Gross Total
        if "Gross Total" in df.columns:
            df["Gross Total"] = (
                df["Gross Total"]
                .astype(str)
                .str.replace("Dr", "", regex=False)
                .str.replace("Cr", "", regex=False)
                .str.replace(",", "", regex=False)
            )
            df["Gross Total"] = pd.to_numeric(df["Gross Total"], errors="coerce")

        # Extract quantity
        if "Quantity" in df.columns:
            df["Quantity Ordered"] = (
                df["Quantity"].astype(str).str.extract(r"(\d+)")[0].astype(float)
            )

        # Split invoices vs items
        invoice_rows = df[df["Gross Total"].notna()].copy()
        item_rows = df[df["Gross Total"].isna() & df["Value"].notna()].copy()

        invoice_rows["Store"] = invoice_rows["Particulars"]
        invoice_rows.rename(columns={"Gross Total": "Amount"}, inplace=True)
        invoice_rows = invoice_rows[
            ["Date", "Store", "Voucher No.", "Amount", "Quantity Ordered"]
        ]

        item_rows = item_rows[
            ["Voucher No.", "Particulars", "Quantity", "Rate", "Value"]
        ].rename(columns={"Particulars": "Product", "Value": "Line Value"})

        all_data.append({"invoices": invoice_rows, "items": item_rows})

    invoices = pd.concat([d["invoices"] for d in all_data], ignore_index=True)
    items = pd.concat([d["items"] for d in all_data], ignore_index=True)
    return {"invoices": invoices, "items": items}


# ---------------------------------------------------------------
# Load data based on source type
if selected_source == "B2B":
    raw_data = load_b2b_data(folder_path)
    df = raw_data["invoices"]
    items_df = raw_data["items"]
else:
    df = load_csv_data(folder_path)
    items_df = pd.DataFrame()

if df.empty:
    st.warning("No valid data found.")
    st.stop()

# ---------------------------------------------------------------
# Sidebar filters
st.sidebar.header("🔍 Filters")

if "Date" in df.columns:
    min_date, max_date = df["Date"].min(), df["Date"].max()
    if pd.notna(min_date) and pd.notna(max_date):
        date_range = st.sidebar.date_input("Select Date Range", [min_date, max_date])
        if len(date_range) == 2:
            start, end = date_range
            df = df[(df["Date"] >= pd.to_datetime(start)) & (df["Date"] <= pd.to_datetime(end))]

if "Store" in df.columns:
    store_list = ["All"] + sorted(df["Store"].dropna().unique().tolist())
    selected_store = st.sidebar.selectbox("Select Store/Vendor", store_list)
    if selected_store != "All":
        df = df[df["Store"] == selected_store]

if "Voucher No." in df.columns:
    inv_search = st.sidebar.text_input("Search Invoice No.")
    if inv_search:
        df = df[df["Voucher No."].astype(str).str.contains(inv_search, case=False)]

# ---------------------------------------------------------------
# Summary Metrics
st.subheader("📈 Summary Metrics")

total_sales = df["Amount"].sum() if "Amount" in df.columns else 0
total_orders = len(df)
unique_stores = df["Store"].nunique() if "Store" in df.columns else 0

col1, col2, col3 = st.columns(3)
col1.metric("💰 Total Sales", f"₹{total_sales:,.0f}")
col2.metric("🧾 Total Orders", total_orders)
col3.metric("🏬 Stores", unique_stores)

st.divider()

# ---------------------------------------------------------------
# Store-wise Sales
if "Store" in df.columns and "Amount" in df.columns:
    st.subheader("🏬 Store-wise Sales")
    store_summary = df.groupby("Store")["Amount"].sum().sort_values(ascending=False)
    st.bar_chart(store_summary, use_container_width=True)

st.divider()

# ---------------------------------------------------------------
# Invoice + Product Details
if selected_source == "B2B":
    st.subheader("📋 Invoice Details")
    for _, row in df.sort_values("Date", ascending=False).iterrows():
        inv = row["Voucher No."]
        with st.expander(f"{inv} — {row['Store']} — ₹{row['Amount']:,.0f}"):
            st.write(f"**Date:** {row['Date'].date()}")
            st.write(f"**Vendor:** {row['Store']}")
            inv_items = items_df[items_df["Voucher No."] == inv]
            if not inv_items.empty:
                total_val = inv_items["Line Value"].sum()
                total_qty = pd.to_numeric(inv_items["Quantity"], errors="coerce").sum()
                st.dataframe(inv_items.reset_index(drop=True), use_container_width=True)
                st.markdown(f"**Total Qty:** {total_qty:.0f}  **Total Value:** ₹{total_val:,.0f}")
            else:
                st.info("No item details for this invoice.")
else:
    st.subheader("📋 Sales Data")
    st.dataframe(df, use_container_width=True)
