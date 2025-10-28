import streamlit as st
import pandas as pd
import os
import numpy as np

st.set_page_config(page_title="Sales Dashboard", layout="wide")

st.title("📊 Consolidated Sales Dashboard")

# --------------------------------------------------------------------
# 📂 Folder selection
folder_path = st.text_input("Enter folder path containing Excel files")

source_type = st.selectbox(
    "Select Source Type",
    ["POS", "Online", "B2B"]
)

if not folder_path or not os.path.isdir(folder_path):
    st.warning("Please enter a valid folder path.")
    st.stop()

# --------------------------------------------------------------------
# 🧮 Data Load Function
def load_data_from_folder(folder, source_type):
    all_data = []

    for file in os.listdir(folder):
        if not file.endswith((".xlsx", ".xls")):
            continue
        file_path = os.path.join(folder, file)

        try:
            df = pd.read_excel(file_path)
        except Exception:
            continue

        # Normalize column names
        df.columns = df.columns.str.strip()

        # ----------------------------------------------------------------
        if source_type == "POS":
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce", dayfirst=True)
            df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
            df["Store"] = df.get("Store", "POS")
            all_data.append(df[["Date", "Store", "Invoice No", "Amount"]])

        # ----------------------------------------------------------------
        elif source_type == "Online":
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce", dayfirst=True)
            df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
            df["Channel"] = df.get("Channel", "Online")
            all_data.append(df[["Date", "Channel", "Order ID", "Amount"]])

        # ----------------------------------------------------------------
        elif source_type == "B2B":
            # Read full sheet and normalize
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce", dayfirst=True)
            df["Voucher No."] = df["Voucher No."].ffill()
            df["Particulars"] = df["Particulars"].ffill()

            df["Value"] = pd.to_numeric(df["Value"], errors="coerce")

            # Clean Gross Total
            df["Gross Total"] = (
                df["Gross Total"]
                .astype(str)
                .str.replace("Dr", "", regex=False)
                .str.replace("Cr", "", regex=False)
                .str.replace(",", "", regex=False)
            )
            df["Gross Total"] = pd.to_numeric(df["Gross Total"], errors="coerce")

            # Extract quantity number
            df["Quantity Ordered"] = (
                df["Quantity"].astype(str).str.extract(r"(\d+)")[0].astype(float)
            )

            # Separate invoice vs. item lines
            invoice_rows = df[df["Gross Total"].notna()].copy()
            item_rows = df[df["Gross Total"].isna() & df["Value"].notna()].copy()

            # Invoice level
            invoice_rows["Store"] = invoice_rows["Particulars"]
            invoice_rows.rename(columns={"Gross Total": "Amount"}, inplace=True)
            invoice_rows = invoice_rows[
                ["Date", "Store", "Voucher No.", "Amount", "Quantity Ordered"]
            ]

            # Item level
            item_rows = item_rows[
                ["Voucher No.", "Particulars", "Quantity", "Rate", "Value"]
            ].rename(columns={"Particulars": "Product", "Value": "Line Value"})

            invoice_rows["Has Items"] = invoice_rows["Voucher No."].isin(
                item_rows["Voucher No."].unique()
            )

            all_data.append({"invoices": invoice_rows, "items": item_rows})

    # ----------------------------------------------------------------
    if source_type == "B2B":
        invoices = pd.concat([d["invoices"] for d in all_data], ignore_index=True)
        items = pd.concat([d["items"] for d in all_data], ignore_index=True)
        return {"invoices": invoices, "items": items}
    elif all_data:
        return pd.concat(all_data, ignore_index=True)
    else:
        return pd.DataFrame()

# --------------------------------------------------------------------
# 🧾 Load the data
raw_data = load_data_from_folder(folder_path, source_type)

if source_type == "B2B":
    invoices_df = raw_data["invoices"]
    items_df = raw_data["items"]
    df = invoices_df.copy()
else:
    df = raw_data
    items_df = pd.DataFrame()

if df.empty:
    st.stop()

# --------------------------------------------------------------------
# 🔍 Filters
st.sidebar.header("🔎 Filters")

min_date = df["Date"].min()
max_date = df["Date"].max()

date_range = st.sidebar.date_input("Select Date Range", [min_date, max_date])
if len(date_range) == 2:
    df = df[(df["Date"] >= pd.to_datetime(date_range[0])) & (df["Date"] <= pd.to_datetime(date_range[1]))]

if "Store" in df.columns:
    store_list = ["All"] + sorted(df["Store"].dropna().unique().tolist())
    selected_store = st.sidebar.selectbox("Select Vendor/Store", store_list)
    if selected_store != "All":
        df = df[df["Store"] == selected_store]

if "Voucher No." in df.columns:
    inv_search = st.sidebar.text_input("Search Invoice No.")
    if inv_search:
        df = df[df["Voucher No."].astype(str).str.contains(inv_search, case=False)]

# --------------------------------------------------------------------
# 📊 Summary Section
st.subheader("📈 Summary Metrics")

total_sales = df["Amount"].sum() if "Amount" in df else 0
unique_invoices = df["Voucher No."].nunique() if "Voucher No." in df else df["Invoice No"].nunique() if "Invoice No" in df else df["Order ID"].nunique() if "Order ID" in df else 0
total_stores = df["Store"].nunique() if "Store" in df else df["Channel"].nunique() if "Channel" in df else 0

col1, col2, col3 = st.columns(3)
col1.metric("💰 Total Sales", f"₹{total_sales:,.0f}")
col2.metric("🧾 Invoices", unique_invoices)
col3.metric("🏬 Stores", total_stores)

# --------------------------------------------------------------------
# 🏪 Store-wise Summary
st.subheader("🏪 Store-wise Sales Summary")

if "Store" in df.columns:
    store_summary = df.groupby("Store")["Amount"].sum().reset_index().sort_values(by="Amount", ascending=False)
    st.dataframe(store_summary, use_container_width=True)
else:
    st.info("Store column not available for this source.")

# --------------------------------------------------------------------
# 📋 Invoice Details (with Drilldown for B2B)
if source_type == "B2B":
    st.subheader("📋 Invoice Details")

    for _, row in df.sort_values("Date", ascending=False).iterrows():
        inv = row["Voucher No."]
        with st.expander(f"{inv} — {row['Store']} — ₹{row['Amount']:,.0f}"):
            st.write(f"**Date:** {row['Date'].date()}")
            st.write(f"**Store:** {row['Store']}")
            inv_items = items_df[items_df["Voucher No."] == inv]
            if not inv_items.empty:
                # Add total summary for each invoice
                total_val = inv_items["Line Value"].sum()
                total_qty = pd.to_numeric(inv_items["Quantity"], errors="coerce").sum()
                st.dataframe(inv_items.reset_index(drop=True), use_container_width=True)
                st.markdown(f"**Total Quantity:** {total_qty:.0f}  **Total Value:** ₹{total_val:,.0f}")
            else:
                st.info("No item details available for this invoice.")
else:
    st.subheader("📋 Invoice Details")
    st.dataframe(df.sort_values("Date", ascending=False), use_container_width=True)
