import streamlit as st
import pandas as pd
import os

# --- Page Setup ---
st.set_page_config(page_title="Unified Sales Dashboard", layout="wide")
st.title("📊 Unified Sales Dashboard")

# --- Folder Paths ---
data_folders = {
    "POS": "sales_data",
    "Online": "online_data",
    "B2B": "B2B"
}

# --- Select Data Source ---
selected_source = st.sidebar.selectbox("Select Data Source", options=list(data_folders.keys()))
folder_path = data_folders[selected_source]

# --- Function to Load Data ---
def load_data_from_folder(folder, source_type):
    all_data = []

    for file in os.listdir(folder):
        if not (file.endswith(".csv") or file.endswith(".xlsx")):
            continue

        path = os.path.join(folder, file)
        df = pd.read_excel(path) if file.endswith(".xlsx") else pd.read_csv(path)
        df.columns = df.columns.astype(str).str.strip()
        df = df.loc[:, ~df.columns.duplicated()]
        df.columns = [c.strip().title() for c in df.columns]

        if source_type == "B2B":
            # Keep only rows that look like vendor/invoice summary lines
            df_filtered = df[df["Voucher No."].notna() | df["Gross Total"].notna()].copy()
            df_filtered["Store"] = df_filtered["Particulars"]
            df_filtered["Date"] = pd.to_datetime(df_filtered["Date"], errors="coerce", dayfirst=True)

            # Clean numeric
            df_filtered["Amount"] = (
                df_filtered["Gross Total"]
                .astype(str)
                .str.replace("Dr", "", regex=False)
                .str.replace("Cr", "", regex=False)
                .str.replace(",", "", regex=False)
            )
            df_filtered["Amount"] = pd.to_numeric(df_filtered["Amount"], errors="coerce")

            df_filtered["Quantity Ordered"] = (
                df_filtered["Quantity"]
                .astype(str)
                .str.extract(r'(\d+)')[0]
                .astype(float)
            )

            df_filtered = df_filtered[["Date", "Store", "Voucher No.", "Amount", "Quantity Ordered"]]
            all_data.append(df_filtered)

        else:
            # --- POS / Online normalization ---
            if "Date" in df.columns:
                df["Date"] = pd.to_datetime(df["Date"], errors="coerce", dayfirst=True)
            for num_col in ["Amount", "Quantity Ordered"]:
                if num_col in df.columns:
                    df[num_col] = pd.to_numeric(df[num_col], errors="coerce")

            all_data.append(df)

    if all_data:
        return pd.concat(all_data, ignore_index=True)
    else:
        st.warning(f"No valid data found in {folder}")
        return pd.DataFrame()

# --- Load Selected Data ---
df = load_data_from_folder(folder_path, selected_source)
if df.empty:
    st.stop()

# --- Sidebar Filters ---
st.sidebar.header("🔍 Filters")

# Date filter
if "Date" in df.columns and df["Date"].notna().any():
    min_date, max_date = df["Date"].min(), df["Date"].max()
    date_range = st.sidebar.date_input("Select Date Range", [min_date, max_date])
    if len(date_range) == 2:
        start, end = date_range
        df = df[(df["Date"] >= pd.to_datetime(start)) & (df["Date"] <= pd.to_datetime(end))]

# Vendor filter
if "Store" in df.columns:
    store_options = sorted(df["Store"].dropna().unique())
    selected_stores = st.sidebar.multiselect("Select Vendor(s)", store_options, default=store_options)
    df = df[df["Store"].isin(selected_stores)]

# Invoice search
if "Voucher No." in df.columns:
    invoice_search = st.sidebar.text_input("Search Invoice No.")
    if invoice_search:
        df = df[df["Voucher No."].astype(str).str.contains(invoice_search, case=False, na=False)]

# --- 1️⃣ Summary Metrics ---
st.subheader("📈 Summary Metrics")
total_sales = df["Amount"].sum() if "Amount" in df.columns else 0
total_invoices = df["Voucher No."].nunique() if "Voucher No." in df.columns else 0
unique_vendors = df["Store"].nunique() if "Store" in df.columns else 0

col1, col2, col3 = st.columns(3)
col1.metric("💰 Total Sales", f"₹{total_sales:,.0f}")
col2.metric("🧾 Total Invoices", total_invoices)
col3.metric("🏬 Vendors", unique_vendors)

st.divider()

# --- 2️⃣ Vendor-wise Summary ---
if "Store" in df.columns and "Amount" in df.columns:
    st.subheader("🏬 Vendor-wise Sales Summary")
    vendor_summary = (
        df.groupby("Store")["Amount"]
        .sum()
        .sort_values(ascending=False)
        .reset_index()
    )
    st.dataframe(vendor_summary, use_container_width=True)
    st.bar_chart(vendor_summary.set_index("Store"), use_container_width=True)

st.divider()

# --- 3️⃣ Invoice Details ---
if "Voucher No." in df.columns:
    st.subheader("📋 Invoice Details")
    st.dataframe(
        df.sort_values(by="Date", ascending=False),
        use_container_width=True,
    )

st.divider()
