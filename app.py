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

# Base path for all folders
base_path = "/mount/src/sales-dashboard"

# Helper for reading files
def load_files(folder):
    if not os.path.exists(folder):
        return pd.DataFrame()
    files = [os.path.join(folder, f) for f in os.listdir(folder) if f.endswith((".csv", ".xlsx"))]
    dfs = []
    for file in files:
        try:
            df = pd.read_excel(file) if file.endswith(".xlsx") else pd.read_csv(file)
            df["SourceFile"] = os.path.basename(file)
            dfs.append(df)
        except Exception as e:
            st.warning(f"Error reading {file}: {e}")
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

# --------------------------------------------------
# ========== SALES DASHBOARD ==========
# --------------------------------------------------
if not dashboard_type:

    st.header("🛒 Sales Dashboard")

    data_source = st.selectbox("Select Data Source", ["POS", "Online", "B2B"])

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

    # Date column detection
    date_cols = [c for c in df.columns if "date" in c.lower()]
    date_col = date_cols[0] if date_cols else None
    if date_col:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")

    # Numeric conversions
    for col in ["Amount", "Quantity Ordered"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Store filter
    if "Store" in df.columns:
        store = st.selectbox("Filter by Store", ["All"] + sorted(df["Store"].dropna().unique().tolist()))
        if store != "All":
            df = df[df["Store"] == store]

    # Date range filter
    if date_col:
        dr = st.date_input("Date Range", [df[date_col].min(), df[date_col].max()])
        if len(dr) == 2:
            s, e = dr
            df = df[(df[date_col].dt.date >= s) & (df[date_col].dt.date <= e)]

    # Summary
    st.subheader("📈 Summary")
    total_sales = df["Amount"].sum() if "Amount" in df.columns else 0
    total_qty = df["Quantity Ordered"].sum() if "Quantity Ordered" in df.columns else 0

    c1, c2 = st.columns(2)
    c1.metric("Total Qty Sold", f"{total_qty:,.0f}")
    c2.metric("Total Sales", f"₹{total_sales:,.0f}")

    # Store-wise summary
    if "Store" in df.columns:
        st.subheader("🏬 Store Summary")
        st.dataframe(df.groupby("Store")["Amount"].sum().reset_index())

    # Product-wise summary
    if "Product" in df.columns and "Quantity Ordered" in df.columns:
        st.subheader("📦 Product Summary")
        st.dataframe(
            df.groupby("Product")
              .agg({"Quantity Ordered": "sum", "Amount": "sum"})
              .reset_index()
        )

# --------------------------------------------------
# ========== INVENTORY DASHBOARD ==========
# --------------------------------------------------
else:
    st.header("📦 Inventory Dashboard")

    inv_folder = os.path.join(base_path, "Inventory")
    inv = load_files(inv_folder)

    if inv.empty:
        st.warning("No inventory found.")
        st.stop()

    inv.columns = [str(c).strip() for c in inv.columns]

    # Date detection
    date_cols = [c for c in inv.columns if "date" in c.lower()]
    date_col = date_cols[0] if date_cols else None

    if date_col:
        inv[date_col] = pd.to_datetime(inv[date_col], errors="coerce")

    # Category Column (from your file)
    category_col = "Category Name" if "Category Name" in inv.columns else None

    # Category Filter
    if category_col:
        cat = st.selectbox(
            "Filter by Category",
            ["All"] + sorted(inv[category_col].dropna().unique().tolist())
        )
        if cat != "All":
            inv = inv[inv[category_col] == cat]

    # Date filter
    if date_col:
        dr = st.date_input(
            "Filter by Inventory Date",
            [inv[date_col].min(), inv[date_col].max()]
        )
        if len(dr) == 2:
            s, e = dr
            inv = inv[(inv[date_col].dt.date >= s) & (inv[date_col].dt.date <= e)]

    # Inventory Table
    st.subheader("📄 Inventory Records")
    st.dataframe(inv, use_container_width=True)

    # Quantity column detection
    qty_col = None
    for c in ["Qty", "Quantity", "Stock", "Closing Stock", "Inventory Qty"]:
        if c in inv.columns:
            qty_col = c
            break

    # Inventory Summary
    if qty_col:
        total_stock = inv[qty_col].sum(min_count=1)
        st.metric("Total Stock", f"{total_stock:,.0f}")

    # Category Summary
    if category_col and qty_col:
        st.subheader("📂 Category Level Summary")
        cat_summary = (
            inv.groupby(category_col)[qty_col]
            .sum()
            .reset_index()
            .rename(columns={qty_col: "Total Stock"})
            .sort_values("Total Stock", ascending=False)
        )
        st.dataframe(cat_summary, use_container_width=True)
