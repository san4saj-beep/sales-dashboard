import streamlit as st
import pandas as pd
import os
import numpy as np

# Streamlit Setup
st.set_page_config(page_title="Sales Dashboard", layout="wide")
st.title("📊 Unified Sales Dashboard")

# Select data source
data_source = st.selectbox("Select Data Source", ["POS", "Online", "B2B"])

# Define folder paths
base_path = "/mount/src/sales-dashboard"
folders = {
    "POS": os.path.join(base_path, "sales_data"),
    "Online": os.path.join(base_path, "online_data"),
    "B2B": os.path.join(base_path, "B2B"),
}

folder_path = folders[data_source]

# Helper to load all files from a folder
def load_data_from_folder(folder):
    if not os.path.exists(folder):
        return pd.DataFrame()
    all_files = [
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if f.endswith((".xlsx", ".csv"))
    ]
    dfs = []
    for file in all_files:
        try:
            df = pd.read_excel(file) if file.endswith(".xlsx") else pd.read_csv(file)
            df["SourceFile"] = os.path.basename(file)
            dfs.append(df)
        except Exception as e:
            st.warning(f"⚠️ Could not read {file}: {e}")
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

# --------------------------------------------------
# POS / ONLINE SECTION (UPDATED)
# --------------------------------------------------
if data_source in ["POS", "Online"]:
    df = load_data_from_folder(folder_path)

    if df.empty:
        st.warning(f"No data found in {folder_path}")
        st.stop()

    # Normalize columns
    df.columns = [str(c).strip() for c in df.columns]

    # Date parsing
    date_cols = [c for c in df.columns if "date" in c.lower()]
    if date_cols:
        df[date_cols[0]] = pd.to_datetime(df[date_cols[0]], errors="coerce")

    # Numeric parsing
    if "Amount" in df.columns:
        df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
    if "Quantity Ordered" in df.columns:
        df["Quantity Ordered"] = pd.to_numeric(df["Quantity Ordered"], errors="coerce")

    # Filters
    store_filter = "All"
    if "Store" in df.columns:
        store_filter = st.selectbox("Filter by Store", ["All"] + sorted(df["Store"].dropna().unique().tolist()))
    date_filter = st.date_input("Filter by Date", [])

    filtered_df = df.copy()
    if store_filter != "All" and "Store" in df.columns:
        filtered_df = filtered_df[filtered_df["Store"] == store_filter]
    if date_filter and date_cols:
        if isinstance(date_filter, (list, tuple)) and len(date_filter) > 0:
            selected_dates = [d for d in date_filter]
            filtered_df = filtered_df[filtered_df[date_cols[0]].dt.date.isin(selected_dates)]
        else:
            filtered_df = filtered_df[filtered_df[date_cols[0]].dt.date == date_filter]

    # --- Summary Metrics ---
    total_sales = filtered_df["Amount"].sum() if "Amount" in filtered_df.columns else 0
    total_qty = filtered_df["Quantity Ordered"].sum() if "Quantity Ordered" in filtered_df.columns else 0

    st.markdown("### 📈 Overall Summary")
    c1, c2 = st.columns(2)
    c1.metric("💰 Total Sales", f"₹{total_sales:,.0f}")
    c2.metric("📦 Total Quantity Sold", f"{total_qty:,.0f}")

    # --- Store-wise Summary ---
    if "Store" in filtered_df.columns:
        st.markdown("### 🏬 Store-wise Sales Summary")
        store_summary = (
            filtered_df.groupby("Store", as_index=False)["Amount"]
            .sum()
            .rename(columns={"Amount": "Total Sales"})
            .sort_values("Total Sales", ascending=False)
        )
        st.dataframe(store_summary, use_container_width=True)
        st.bar_chart(store_summary.set_index("Store")["Total Sales"])

    # --- Product-wise Summary ---
    product_col = "Product" if "Product" in filtered_df.columns else None
    if product_col and "Amount" in filtered_df.columns:
        st.markdown("### 🧾 Product-wise Sales Summary")
        product_summary = (
            filtered_df.groupby(product_col, as_index=False)["Amount"]
            .sum()
            .rename(columns={"Amount": "Total Sales"})
            .sort_values("Total Sales", ascending=False)
        )
        st.dataframe(product_summary, use_container_width=True)

# --------------------------------------------------
# B2B SECTION (unchanged)
# --------------------------------------------------
elif data_source == "B2B":
    raw = load_data_from_folder(folder_path)

    if raw.empty:
        st.warning(f"No data found in {folder_path}")
        st.stop()

    raw.columns = [str(c).strip() for c in raw.columns]

    if "Voucher No." not in raw.columns or "Particulars" not in raw.columns:
        st.error("B2B files must include 'Voucher No.' and 'Particulars' columns.")
        st.stop()

    raw["Voucher No."] = raw["Voucher No."].ffill()
    raw["Particulars"] = raw["Particulars"].ffill()
    if "Date" in raw.columns:
        raw["Date"] = pd.to_datetime(raw["Date"], errors="coerce", dayfirst=True)

    value_col = None
    for candidate in ["Value", "Line Value", "Amount", "Gross Total"]:
        if candidate in raw.columns:
            value_col = candidate
            break

    item_mask = pd.Series(False, index=raw.index)
    if "Value" in raw.columns:
        item_mask = item_mask | raw["Value"].notna()
    if "Quantity" in raw.columns:
        item_mask = item_mask | raw["Quantity"].notna()
    if "Gross Total" in raw.columns:
        header_mask = raw["Gross Total"].notna()
        item_mask = item_mask & (~header_mask)

    items_df = raw[item_mask].copy()
    for col in ["Voucher No.", "Particulars", "Quantity", "Rate", value_col]:
        if col not in items_df.columns:
            items_df[col] = np.nan

    if value_col:
        items_df[value_col] = items_df[value_col].astype(str).str.replace("Dr", "", regex=False).str.replace("Cr", "", regex=False).str.replace(",", "", regex=False)
        items_df["LineValueNumeric"] = pd.to_numeric(items_df[value_col], errors="coerce")
    else:
        items_df["LineValueNumeric"] = pd.NA

    if "Quantity" in items_df.columns:
        items_df["QuantityNumeric"] = pd.to_numeric(items_df["Quantity"].astype(str).str.extra_
