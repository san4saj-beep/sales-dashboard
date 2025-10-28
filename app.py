import streamlit as st
import pandas as pd
import os
import re

st.set_page_config(page_title="Sales Dashboard", layout="wide")

st.title("📊 Multi-Source Sales Dashboard")

# --- Folder Paths ---
data_folders = {
    "POS": "sales_data",
    "Online": "online_data",
    "B2B": "B2B"
}

# --- Select Platform ---
platform = st.sidebar.selectbox("Select Data Source", options=list(data_folders.keys()))
folder_path = data_folders[platform]

# --- Load Data ---
def load_excel_files(folder):
    all_data = []
    for file in os.listdir(folder):
        if file.endswith(".xlsx") or file.endswith(".xls"):
            file_path = os.path.join(folder, file)
            try:
                df = pd.read_excel(file_path)
                df["SourceFile"] = file
                all_data.append(df)
            except Exception as e:
                st.warning(f"⚠️ Could not read {file}: {e}")
    return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()

# ---------------------------
# POS / ONLINE PROCESSING
# ---------------------------
def process_pos_online_data(df):
    if df.empty:
        st.warning("No data found in POS/Online folder.")
        return

    # Convert Date and Amount safely
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

    if "Amount" in df.columns:
        df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")

    # --- Summary ---
    total_sales = df["Amount"].sum()
    total_qty = df["Quantity Ordered"].sum() if "Quantity Ordered" in df.columns else 0

    st.metric("Total Sales", f"₹{total_sales:,.0f}")
    st.metric("Total Quantity Sold", f"{int(total_qty)}")

    # --- Store Level Summary ---
    if "Store" in df.columns:
        st.subheader("🏪 Store-wise Sales Summary")
        store_summary = df.groupby("Store")["Amount"].sum().reset_index().sort_values("Amount", ascending=False)
        st.dataframe(store_summary, use_container_width=True)

    # --- Product Level Summary ---
    if "Product" in df.columns:
        st.subheader("📦 Product-wise Summary")
        product_summary = df.groupby("Product")[["Quantity Ordered", "Amount"]].sum().reset_index()
        st.dataframe(product_summary, use_container_width=True)

    # --- Date Filter ---
    if "Date" in df.columns:
        st.subheader("📅 Filter by Date")
        date_filter = st.date_input("Select Date Range", [])
        if len(date_filter) == 2:
            start_date, end_date = date_filter
            filtered_df = df[(df["Date"] >= pd.Timestamp(start_date)) & (df["Date"] <= pd.Timestamp(end_date))]
            st.dataframe(filtered_df)

# ---------------------------
# B2B PROCESSING
# ---------------------------
def process_b2b_data(df):
    if df.empty:
        st.warning("No data found in B2B folder.")
        return

    # Forward fill key details like Date, Vendor, and Invoice
    df["Date"] = df["Date"].ffill()
    df["Particulars"] = df["Particulars"].ffill()
    df["Voucher No."] = df["Voucher No."].ffill()

    # Identify item rows
    items_df = df[df["Particulars"].isna() & df["Voucher No."].isna()].copy()
    items_df["Invoice No"] = df["Voucher No."].ffill()
    items_df["Vendor"] = df["Particulars"].ffill()
    items_df["Date"] = df["Date"].ffill()

    # Extract numeric quantity from Quantity column
    items_df["QuantityNumeric"] = pd.to_numeric(
        items_df["Quantity"].astype(str).str.extract(r"(\d+)")[0], errors="coerce"
    )

    # Extract numeric value
    items_df["ValueNumeric"] = pd.to_numeric(
        items_df["Value"].astype(str).str.replace(",", ""), errors="coerce"
    )

    # --- Summary Metrics ---
    total_value = items_df["ValueNumeric"].sum()
    total_qty = items_df["QuantityNumeric"].sum()
    st.metric("Total B2B Sales", f"₹{total_value:,.0f}")
    st.metric("Total Quantity Sold", f"{int(total_qty)}")

    # --- Vendor-wise Summary ---
    vendor_summary = items_df.groupby("Vendor")[["QuantityNumeric", "ValueNumeric"]].sum().reset_index()
    vendor_summary.columns = ["Vendor", "Total Qty", "Total Value"]
    st.subheader("🏢 Vendor-wise Summary")
    st.dataframe(vendor_summary, use_container_width=True)

    # --- Date Filter ---
    st.subheader("📅 Filter by Date")
    items_df["Date"] = pd.to_datetime(items_df["Date"], errors="coerce")
    date_filter = st.date_input("Select Date Range", [])
    filtered_df = items_df
    if len(date_filter) == 2:
        start_date, end_date = date_filter
        filtered_df = items_df[(items_df["Date"] >= pd.Timestamp(start_date)) & (items_df["Date"] <= pd.Timestamp(end_date))]

    # --- Invoice Selector ---
    st.subheader("📜 Invoice Details")
    invoice_list = filtered_df["Invoice No"].dropna().unique().tolist()
    selected_invoice = st.selectbox("Select Invoice No", invoice_list)
    if selected_invoice:
        invoice_data = filtered_df[filtered_df["Invoice No"] == selected_invoice]
        st.dataframe(invoice_data[["Date", "Vendor", "Invoice No", "Value", "Quantity", "Rate"]], use_container_width=True)

# ---------------------------
# MAIN EXECUTION
# ---------------------------
if os.path.exists(folder_path):
    df = load_excel_files(folder_path)
    if platform in ["sales_data", "online_data"]:
        process_pos_online_data(df)
    elif platform == "B2B":
        process_b2b_data(df)
else:
    st.error(f"❌ Folder '{folder_path}' not found. Please check your directory.")
