import streamlit as st
import pandas as pd
import os
import numpy as np

# --------------------------------------------------
# STREAMLIT PAGE SETUP
# --------------------------------------------------
st.set_page_config(page_title="Unified Dashboard", layout="wide")
st.title("📊 Unified Sales + Inventory Dashboard")

# --------------------------------------------------
# TOP-LEVEL SELECTION: SALES OR INVENTORY
# --------------------------------------------------
dashboard_type = st.checkbox("Show Inventory Dashboard Instead of Sales", value=False)

# Base folder
base_path = "/mount/src/sales-dashboard"

# --------------------------------------------------
# Helper: Load all CSV/XLSX from a folder
# --------------------------------------------------
def load_files(folder):
    if not os.path.exists(folder):
        return pd.DataFrame()

    files = [
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if f.endswith((".csv", ".xlsx"))
    ]

    all_dfs = []
    for f in files:
        try:
            df = pd.read_excel(f) if f.endswith(".xlsx") else pd.read_csv(f)
            df["SourceFile"] = os.path.basename(f)
            all_dfs.append(df)
        except Exception as e:
            st.warning(f"Cannot read {f}: {e}")

    return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()


# --------------------------------------------------
# ========== SALES DASHBOARD ==========
# --------------------------------------------------

if not dashboard_type:

    st.header("🛒 Sales Dashboard")

    data_source = st.selectbox(
        "Select Data Source",
        ["POS", "Online", "B2B"]
    )

    folders = {
        "POS": os.path.join(base_path, "sales_data"),
        "Online": os.path.join(base_path, "online_data"),
        "B2B": os.path.join(base_path, "B2B"),
    }

    df = load_files(folders[data_source])

    if df.empty:
        st.warning("No data found.")
        st.stop()

    df.columns = [str(c).strip() for c in df.columns]

    # Detect date column
    date_cols = [c for c in df.columns if "date" in c.lower()]
    date_col = date_cols[0] if date_cols else None
    if date_col:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")

    # Numeric column cleanup
    for num_col in ["Amount", "Quantity Ordered", "Qty"]:
        if num_col in df.columns:
            df[num_col] = pd.to_numeric(df[num_col], errors="coerce")

    # -------------------------------
    # STORE FILTER (if store exists)
    # -------------------------------
    if "Store" in df.columns:
        store_list = ["All"] + sorted(df["Store"].dropna().unique().tolist())
        store_filter = st.selectbox("Filter by Store", store_list)
        if store_filter != "All":
            df = df[df["Store"] == store_filter]

    # -------------------------------
    # DATE RANGE FILTER
    # -------------------------------
    if date_col:
        dmin, dmax = df[date_col].min(), df[date_col].max()
        date_range = st.date_input(
            "Select Date Range",
            value=[dmin, dmax]
        )
        if len(date_range) == 2:
            s, e = date_range
            df = df[(df[date_col].dt.date >= s) & (df[date_col].dt.date <= e)]

    # -------------------------------
    # SUMMARY BLOCK
    # -------------------------------
    st.subheader("📈 Summary")

    total_sales = df["Amount"].sum() if "Amount" in df.columns else 0
    total_qty = df["Quantity Ordered"].sum() if "Quantity Ordered" in df.columns else 0

    c1, c2 = st.columns(2)
    c1.metric("Total Qty Sold", f"{total_qty:,.0f}")
    c2.metric("Total Sales", f"₹{total_sales:,.0f}")

    # -------------------------------
    # STORE-WISE SUMMARY
    # -------------------------------
    if "Store" in df.columns:
        st.subheader("🏬 Store-wise Sales")
        store_summary = df.groupby("Store")["Amount"].sum().reset_index()
        st.dataframe(store_summary, use_container_width=True)

    # -------------------------------
    # PRODUCT-WISE SUMMARY
    # -------------------------------
    if "Product" in df.columns:
        st.subheader("📦 Product-wise Sales")
        group_cols = {}
        if "Quantity Ordered" in df.columns:
            group_cols["Quantity Ordered"] = "sum"
        if "Amount" in df.columns:
            group_cols["Amount"] = "sum"

        prod_summary = df.groupby("Product").agg(group_cols).reset_index()
        st.dataframe(prod_summary, use_container_width=True)

    # END SALES BLOCK
    st.stop()


# --------------------------------------------------
# ========== INVENTORY DASHBOARD ==========
# --------------------------------------------------

st.header("📦 Inventory Dashboard")

inventory_folder = os.path.join(base_path, "Inventory")
inv = load_files(inventory_folder)

if inv.empty:
    st.warning("No inventory data found.")
    st.stop()

inv.columns = [str(c).strip() for c in inv.columns]

# -------------------------------
# Detect Date Column
# -------------------------------
date_cols = [c for c in inv.columns if "date" in c.lower()]
date_col = date_cols[0] if date_cols else None

if date_col:
    inv[date_col] = pd.to_datetime(inv[date_col], errors="coerce")

# -------------------------------
# CATEGORY COLUMN DETECTION
# -------------------------------
category_col = None
for c in ["Category", "category", "Item Category", "Group"]:
    if c in inv.columns:
        category_col = c
        break

# -------------------------------
# CATEGORY FILTER
# -------------------------------
if category_col:
    cats = ["All"] + sorted(inv[category_col].dropna().unique().tolist())
    category_filter = st.selectbox("Filter by Category", cats)

    if category_filter != "All":
        inv = inv[inv[category_col] == category_filter]

# -------------------------------
# DATE FILTER
# -------------------------------
if date_col:
    dmin, dmax = inv[date_col].min(), inv[date_col].max()
    date_range = st.date_input("Select Inventory Date", value=[dmin, dmax])

    if len(date_range) == 2:
        s, e = date_range
        inv = inv[(inv[date_col].dt.date >= s) & (inv[date_col].dt.date <= e)]

# -------------------------------
# TABLE VIEW
# -------------------------------
st.subheader("📄 Inventory Records")
st.dataframe(inv, use_container_width=True)

# -------------------------------
# QUANTITY COLUMN DETECTION
# -------------------------------
qty_col = None
for q in ["Qty", "Quantity", "Stock", "Closing Stock"]:
    if q in inv.columns:
        qty_col = q
        break

# -------------------------------
# TOTAL INVENTORY SUMMARY
# -------------------------------
if qty_col:
    total_stock = inv[qty_col].sum(min_count=1)
    st.metric("Total Stock", f"{total_stock:,.0f}")

# -------------------------------
# CATEGORY LEVEL SUMMARY
# -------------------------------
if category_col and qty_col:
    st.subheader("📂 Category Level Inventory Summary")

    cat_summary = (
        inv.groupby(category_col)[qty_col]
        .sum()
        .reset_index()
        .rename(columns={qty_col: "Total Stock"})
        .sort_values("Total Stock", ascending=False)
    )

    st.dataframe(cat_summary, use_container_width=True)
