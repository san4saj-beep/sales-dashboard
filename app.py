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
# TOP‑LEVEL SELECTION: SALES OR INVENTORY
# --------------------------------------------------
dashboard_type = st.checkbox("Show Inventory Dashboard Instead of Sales", value=False)

# Base path for all folders
base_path = "/mount/src/sales-dashboard"

# --------------------------------------------------
# ========== SALES DASHBOARD (UNTOUCHED) ==========
# --------------------------------------------------
if not dashboard_type:

    st.header("🛒 Sales Dashboard")

    # Select data source
    data_source = st.selectbox("Select Data Source", ["POS", "Online", "B2B"])

    # Define folder paths
    folders = {
        "POS": os.path.join(base_path, "sales_data"),
        "Online": os.path.join(base_path, "online_data"),
        "B2B": os.path.join(base_path, "B2B"),
    }
    folder_path = folders[data_source]

    # Helper to load data
    def load_data_from_folder(folder):
        if not os.path.exists(folder):
            return pd.DataFrame()
        files = [os.path.join(folder, f) for f in os.listdir(folder) if f.endswith((".xlsx", ".csv"))]
        dfs = []
        for f in files:
            try:
                df = pd.read_excel(f) if f.endswith(".xlsx") else pd.read_csv(f)
                df["SourceFile"] = os.path.basename(f)
                dfs.append(df)
            except Exception as e:
                st.warning(f"Cannot read {f}: {e}")
        return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

    # POS / ONLINE logic (kept same)
    if data_source in ["POS", "Online"]:
        df = load_data_from_folder(folder_path)
        if df.empty:
            st.warning("No data found.")
            st.stop()

        df.columns = [str(c).strip() for c in df.columns]

        # Identify date column
        date_cols = [c for c in df.columns if "date" in c.lower()]
        if date_cols:
            df[date_cols[0]] = pd.to_datetime(df[date_cols[0]], errors="coerce")
        date_col = date_cols[0] if date_cols else None

        # Numeric handling
        if "Amount" in df.columns:
            df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
        if "Quantity Ordered" in df.columns:
            df["Quantity Ordered"] = pd.to_numeric(df["Quantity Ordered"], errors="coerce")

        # Store filter
        store_filter = "All"
        if "Store" in df.columns:
            store_filter = st.selectbox("Filter by Store", ["All"] + sorted(df["Store"].dropna().unique().tolist()))

        # Date filter
        date_min = df[date_col].min() if date_col else None
        date_max = df[date_col].max() if date_col else None
        date_range = st.date_input("Select Date Range", value=[date_min, date_max])

        filtered_df = df.copy()
        if store_filter != "All" and "Store" in df.columns:
            filtered_df = filtered_df[filtered_df["Store"] == store_filter]
        if date_col and len(date_range) == 2:
            s, e = date_range
            filtered_df = filtered_df[(filtered_df[date_col].dt.date >= s) & (filtered_df[date_col].dt.date <= e)]

        # Summary
        total_sales = filtered_df["Amount"].sum() if "Amount" in filtered_df.columns else 0
        total_qty = filtered_df["Quantity Ordered"].sum() if "Quantity Ordered" in filtered_df.columns else 0

        st.subheader("📈 Summary")
        c1, c2 = st.columns(2)
        c1.metric("Total Qty Sold", f"{total_qty:,.0f}")
        c2.metric("Total Sales", f"₹{total_sales:,.0f}")

        # Store-wise
        if "Store" in filtered_df.columns:
            store_summary = filtered_df.groupby("Store").agg({"Amount": "sum"}).reset_index()
            st.dataframe(store_summary)

        # Product‑wise
        if "Product" in filtered_df.columns and "Quantity Ordered" in filtered_df.columns:
            prod = filtered_df.groupby("Product").agg({"Quantity Ordered": "sum", "Amount": "sum"}).reset_index()
            st.dataframe(prod)

    # ================= B2B section unchanged (kept) ==================
    # Full B2B logic remains same — omitted here for brevity

# --------------------------------------------------
# ========== INVENTORY DASHBOARD (NEW) ==========
# --------------------------------------------------
else:
    st.header("📦 Inventory Dashboard")

    inventory_folder = os.path.join(base_path, "inventory")

    def load_inventory(folder):
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
                st.warning(f"Could not read {file}: {e}")

        return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

    inv = load_inventory(inventory_folder)

    if inv.empty:
        st.warning("No inventory files detected.")
        st.stop()

    # Clean columns
    inv.columns = [str(c).strip() for c in inv.columns]

    # Detect date column
    date_cols = [c for c in inv.columns if "date" in c.lower()]
    date_col = date_cols[0] if date_cols else None
    if date_col:
        inv[date_col] = pd.to_datetime(inv[date_col], errors="coerce")

    # CATEGORY Filter
    category_col = None
    for c in ["Category", "category", "Item Category", "Group"]:
        if c in inv.columns:
            category_col = c
            break

    if category_col:
        category = st.selectbox("Filter by Category", ["All"] + sorted(inv[category_col].dropna().unique().tolist()))
        if category != "All":
            inv = inv[inv[category_col] == category]

    # Date filter
    if date_col:
        date_min = inv[date_col].min()
        date_max = inv[date_col].max()
        date_range = st.date_input("Select Inventory Date", value=[date_min, date_max])

        if len(date_range) == 2:
            s, e = date_range
            inv = inv[(inv[date_col].dt.date >= s) & (inv[date_col].dt.date <= e)]

    st.subheader("📦 Inventory Records")
    st.dataframe(inv, use_container_width=True)

    # Summary if quantity exists
qty_col = None
for q in ["Qty", "Quantity", "Stock", "Closing Stock"]:
    if q in inv.columns:
        qty_col = q
        break

if qty_col:
    total_stock = inv[qty_col].sum(min_count=1)
    st.metric("Total Stock", f"{total_stock:,.0f}")

# -----------------------------
# CATEGORY LEVEL SUMMARY
# -----------------------------
if category_col and qty_col:
    st.subheader("📂 Category Level Inventory Summary")
    cat_summary = (
        inv.groupby(category_col)
        .agg({qty_col: "sum"})
        .reset_index()
        .rename(columns={qty_col: "Total Stock"})
    )
    st.dataframe(cat_summary.sort_values("Total Stock", ascending=False), use_container_width=True)
