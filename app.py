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
    "B2B": "B2B"   # updated folder name
}

# --- Dropdown ---
selected_source = st.sidebar.selectbox("Select Data Source", options=list(data_folders.keys()))
folder_path = data_folders[selected_source]

# --- POS/Online Loader ---
def load_data_from_folder(folder):
    all_data = []
    for file in os.listdir(folder):
        if file.endswith(".csv"):
            path = os.path.join(folder, file)
            df = pd.read_csv(path)

            # clean
            df.columns = df.columns.astype(str).str.strip()
            df = df.loc[:, ~df.columns.duplicated()]
            df.columns = [c.strip().title() for c in df.columns]

            # convert date
            if "Date" in df.columns:
                df["Date"] = pd.to_datetime(df["Date"], errors="coerce", dayfirst=True)

            # convert numeric
            for col in ["Amount", "Quantity Ordered"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            all_data.append(df)
    if all_data:
        return pd.concat(all_data, ignore_index=True)
    else:
        st.warning(f"No CSV files found in {folder}")
        return pd.DataFrame()

# --- B2B Loader (working version) ---
def load_b2b_data(folder):
    all_data = []
    for file in os.listdir(folder):
        if file.endswith(".xlsx"):
            path = os.path.join(folder, file)
            xl = pd.read_excel(path, header=None)
            current_vendor, current_invoice, date = None, None, None
            rows = []

            for i, row in xl.iterrows():
                # detect new invoice
                if pd.notna(row[0]) and "INV" in str(row[2]):
                    date = pd.to_datetime(row[0], errors="coerce", dayfirst=True)
                    current_vendor = str(row[1]).strip()
                    current_invoice = str(row[2]).strip()

                # detect product rows
                elif isinstance(row[0], str) and "Plaeto" in row[0]:
                    product = row[0].strip()
                    qty = str(row[1])
                    qty_val = pd.to_numeric(str(qty).split()[0], errors="coerce")
                    rate = str(row[2])
                    rate_val = pd.to_numeric(rate.split("/")[0], errors="coerce")
                    value = pd.to_numeric(row[3], errors="coerce")
                    rows.append([date, current_vendor, current_invoice, product, qty_val, rate_val, value])

            df = pd.DataFrame(rows, columns=["Date", "Vendor", "Invoice No", "Product", "Quantity", "Rate", "Value"])
            all_data.append(df)

    if all_data:
        df = pd.concat(all_data, ignore_index=True)
        df["Value"] = pd.to_numeric(df["Value"], errors="coerce")
        df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce")
        return df
    else:
        st.warning("No Excel files found in B2B folder")
        return pd.DataFrame()

# --- Load Correct Dataset ---
if selected_source == "B2B":
    df = load_b2b_data(folder_path)
else:
    df = load_data_from_folder(folder_path)

if df.empty:
    st.stop()

# --- Sidebar Filters ---
st.sidebar.header("🔍 Filters")

# ---------- B2B DASHBOARD ----------
if selected_source == "B2B":
    if "Vendor" in df.columns:
        vendors = sorted(df["Vendor"].dropna().unique())
        selected_vendors = st.sidebar.multiselect("Select Vendor(s)", options=vendors, default=vendors)
        df = df[df["Vendor"].isin(selected_vendors)]

    if "Date" in df.columns:
        min_date, max_date = df["Date"].min(), df["Date"].max()
        if pd.notna(min_date) and pd.notna(max_date):
            date_range = st.sidebar.date_input("Select Date Range", [min_date, max_date])
            if len(date_range) == 2:
                start, end = date_range
                df = df[(df["Date"] >= pd.to_datetime(start)) & (df["Date"] <= pd.to_datetime(end))]

    # --- Summary ---
    st.subheader("📦 B2B Summary Metrics")
    total_sales = df["Value"].sum()
    total_qty = df["Quantity"].sum()
    total_invoices = df["Invoice No"].nunique()
    total_vendors = df["Vendor"].nunique()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Total Sales", f"₹{total_sales:,.0f}")
    c2.metric("📦 Total Quantity", f"{total_qty:,.0f}")
    c3.metric("🧾 Total Invoices", total_invoices)
    c4.metric("🏬 Vendors", total_vendors)

    st.divider()

    # --- Vendor Summary ---
    st.subheader("🏢 Vendor-wise Sales Summary")
    vendor_summary = df.groupby("Vendor")["Value"].sum().sort_values(ascending=False)
    st.bar_chart(vendor_summary, use_container_width=True)

    st.divider()

    # --- Invoice Summary ---
    st.subheader("🧾 Invoice Details")
    invoices = df.groupby("Invoice No").agg({
        "Vendor": "first",
        "Date": "first",
        "Value": "sum"
    }).reset_index().sort_values("Date", ascending=False)

    for _, inv in invoices.iterrows():
        with st.expander(f"{inv['Invoice No']} | {inv['Vendor']} | ₹{inv['Value']:,.0f}"):
            details = df[df["Invoice No"] == inv["Invoice No"]][["Product", "Quantity", "Rate", "Value"]]
            st.dataframe(details, use_container_width=True)

# ---------- POS / ONLINE DASHBOARD ----------
else:
    if "Store" in df.columns:
        stores = sorted(df["Store"].dropna().unique())
        selected_stores = st.sidebar.multiselect("Select Store(s)", options=stores, default=stores)
        df = df[df["Store"].isin(selected_stores)]

    if "Date" in df.columns:
        min_date, max_date = df["Date"].min(), df["Date"].max()
        if pd.notna(min_date) and pd.notna(max_date):
            date_range = st.sidebar.date_input("Select Date Range", [min_date, max_date])
            if len(date_range) == 2:
                start, end = date_range
                df = df[(df["Date"] >= pd.to_datetime(start)) & (df["Date"] <= pd.to_datetime(end))]

    # --- Summary ---
    st.subheader("📈 Summary Metrics")
    total_sales = df["Amount"].sum() if "Amount" in df.columns else 0
    total_orders = len(df)
    unique_stores = df["Store"].nunique() if "Store" in df.columns else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("💰 Total Sales", f"₹{total_sales:,.0f}")
    c2.metric("🧾 Total Orders", total_orders)
    c3.metric("🏬 Stores", unique_stores)

    st.divider()

    # --- Store Summary ---
    if "Store" in df.columns and "Amount" in df.columns:
        st.subheader("🏬 Store-wise Sales")
        store_summary = df.groupby("Store")["Amount"].sum().sort_values(ascending=False)
        st.bar_chart(store_summary, use_container_width=True)

    st.divider()

    # --- Product Summary ---
    if "Product" in df.columns:
        st.subheader("🧾 Product Performance")
        summary_cols = [c for c in ["Quantity Ordered", "Amount"] if c in df.columns]
        product_summary = (
            df.groupby("Product")[summary_cols]
            .sum()
            .sort_values(by=summary_cols[0], ascending=False)
        )
        st.dataframe(product_summary, use_container_width=True)
