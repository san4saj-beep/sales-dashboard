import streamlit as st
import pandas as pd
import os
import numpy as np

st.set_page_config(page_title="Unified Dashboard", layout="wide")

st.title("📊 Sales & Inventory Dashboard")

# --------------------------------------------------
# PATH SETUP
# --------------------------------------------------

base_path = "/mount/src/sales-dashboard"

folders = {
    "POS": os.path.join(base_path, "sales_data"),
    "Online": os.path.join(base_path, "online_data"),
    "B2B": os.path.join(base_path, "B2B"),
    "Inventory": os.path.join(base_path, "inventory")
}

# --------------------------------------------------
# FILE LOADER
# --------------------------------------------------

def load_data_from_folder(folder):

    if not os.path.exists(folder):
        return pd.DataFrame()

    files = [os.path.join(folder,f) for f in os.listdir(folder) if f.endswith((".xlsx",".csv"))]

    dfs = []

    for file in files:

        try:
            if file.endswith(".xlsx"):
                df = pd.read_excel(file)
            else:
                df = pd.read_csv(file)

            df["SourceFile"] = os.path.basename(file)

            dfs.append(df)

        except:
            pass

    if dfs:
        return pd.concat(dfs, ignore_index=True)

    return pd.DataFrame()

# --------------------------------------------------
# SELECT DASHBOARD TYPE
# --------------------------------------------------

dashboard = st.sidebar.selectbox(
    "Select Dashboard",
    ["Sales Dashboard", "Inventory Dashboard"]
)

# ==================================================
# SALES DASHBOARD
# ==================================================

if dashboard == "Sales Dashboard":

    data_source = st.selectbox("Select Sales Source", ["POS","Online","B2B"])

    folder_path = folders[data_source]

    df = load_data_from_folder(folder_path)

    if df.empty:
        st.warning("No data found")
        st.stop()

    df.columns = [str(c).strip() for c in df.columns]

# --------------------------------------------------
# POS / ONLINE SALES
# --------------------------------------------------

    if data_source in ["POS","Online"]:

        # Detect columns

        date_col = None
        for c in df.columns:
            if "date" in c.lower():
                date_col = c
                break

        if date_col:
            df[date_col] = pd.to_datetime(df[date_col], errors="coerce")

        amount_col = None
        for c in ["Amount","Total","Value"]:
            if c in df.columns:
                amount_col = c
                break

        product_col = None
        for c in ["Product","Product Name","Item","Title"]:
            if c in df.columns:
                product_col = c
                break

        store_col = None
        for c in ["Store","Location","Warehouse"]:
            if c in df.columns:
                store_col = c
                break

        qty_col = None
        for c in ["Quantity Ordered","Quantity","Qty"]:
            if c in df.columns:
                qty_col = c
                break

        if qty_col is None:
            df["Quantity Ordered"] = 1
            qty_col = "Quantity Ordered"

        df[qty_col] = pd.to_numeric(df[qty_col], errors="coerce")

        if amount_col:
            df[amount_col] = pd.to_numeric(df[amount_col], errors="coerce")

# --------------------------------------------------
# FILTERS
# --------------------------------------------------

        filtered = df.copy()

        if store_col:
            store = st.selectbox("Store Filter", ["All"] + sorted(df[store_col].dropna().unique()))
            if store != "All":
                filtered = filtered[filtered[store_col]==store]

        if date_col:
            start,end = st.date_input(
                "Date Range",
                [df[date_col].min(), df[date_col].max()]
            )

            filtered = filtered[
                (filtered[date_col].dt.date>=start) &
                (filtered[date_col].dt.date<=end)
            ]

# --------------------------------------------------
# SUMMARY
# --------------------------------------------------

        total_sales = filtered[amount_col].sum() if amount_col else 0
        total_qty = filtered[qty_col].sum()

        st.subheader("📈 Overall Summary")

        c1,c2 = st.columns(2)

        c1.metric("Total Quantity", f"{total_qty:,.0f}")
        c2.metric("Total Sales", f"₹{total_sales:,.0f}")

# --------------------------------------------------
# STORE SUMMARY
# --------------------------------------------------

        if store_col:

            st.subheader("🏬 Store Sales Summary")

            store_summary = (
                filtered.groupby(store_col)
                .agg({amount_col:"sum"})
                .reset_index()
                .rename(columns={amount_col:"Total Sales"})
            )

            st.dataframe(store_summary.sort_values("Total Sales",ascending=False))

# --------------------------------------------------
# PRODUCT SUMMARY
# --------------------------------------------------

        if product_col:

            st.subheader("🏷 Product Sales Summary")

            prod = (
                filtered.groupby(product_col)
                .agg({qty_col:"sum",amount_col:"sum"})
                .reset_index()
                .rename(columns={
                    qty_col:"Quantity",
                    amount_col:"Sales"
                })
            )

            st.dataframe(prod.sort_values("Sales",ascending=False))

# ==================================================
# B2B SALES
# ==================================================

    elif data_source == "B2B":

        raw = df

        if "Voucher No." not in raw.columns:
            st.error("Voucher No column missing")
            st.stop()

        raw["Voucher No."] = raw["Voucher No."].ffill()
        raw["Particulars"] = raw["Particulars"].ffill()

        if "Date" in raw.columns:
            raw["Date"] = pd.to_datetime(raw["Date"], errors="coerce", dayfirst=True)

        if "Value" in raw.columns:
            raw.rename(columns={"Value":"PreTax"}, inplace=True)

        raw["PreTax"] = (
            raw["PreTax"]
            .astype(str)
            .str.replace("Dr","")
            .str.replace("Cr","")
            .str.replace(",","")
        )

        raw["PreTax"] = pd.to_numeric(raw["PreTax"], errors="coerce")

        invoices = []

        vouchers = raw["Voucher No."].dropna().unique()

        for v in vouchers:

            inv = raw[raw["Voucher No."]==v]

            header = inv[inv["Gross Total"].notna()].head(1)

            if header.empty:
                header = inv.head(1)

            gross = header["Gross Total"].astype(str).str.replace("Dr","").str.replace("Cr","").str.replace(",","")

            try:
                gross = float(gross.values[0])
            except:
                gross = 0

            invoices.append({
                "Date":header["Date"].values[0],
                "Vendor":header["Particulars"].values[0],
                "Invoice":v,
                "Items":len(inv),
                "PreTax":inv["PreTax"].sum(),
                "Gross":gross
            })

        inv_df = pd.DataFrame(invoices)

        st.subheader("B2B Summary")

        c1,c2,c3,c4 = st.columns(4)

        c1.metric("Invoices",len(inv_df))
        c2.metric("Vendors",inv_df["Vendor"].nunique())
        c3.metric("Pretax Sales",f"₹{inv_df['PreTax'].sum():,.0f}")
        c4.metric("Gross Sales",f"₹{inv_df['Gross'].sum():,.0f}")

        st.dataframe(inv_df.sort_values("Date",ascending=False))

# ==================================================
# INVENTORY DASHBOARD
# ==================================================

elif dashboard == "Inventory Dashboard":

    folder_path = folders["Inventory"]

    df = load_data_from_folder(folder_path)

    if df.empty:
        st.warning("No inventory files found")
        st.stop()

    df.columns = [str(c).strip() for c in df.columns]

# --------------------------------------------------
# REQUIRED COLUMNS
# --------------------------------------------------

    rename_map = {
        "Item Type Name":"Product",
        "Item SkuCode":"SKU",
        "Category Name":"Category",
        "Inventory":"Stock",
        "Cost Price":"Cost",
        "Date":"Date"
    }

    df.rename(columns=rename_map, inplace=True)

    df["Stock"] = pd.to_numeric(df["Stock"], errors="coerce")
    df["Cost"] = pd.to_numeric(df["Cost"], errors="coerce")

    df["Inventory Value"] = df["Stock"] * df["Cost"]

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

# --------------------------------------------------
# FILTERS
# --------------------------------------------------

    category = st.selectbox(
        "Category Filter",
        ["All"] + sorted(df["Category"].dropna().unique())
    )

    if category != "All":
        df = df[df["Category"]==category]

# --------------------------------------------------
# DATE FILTER
# --------------------------------------------------

    dates = sorted(df["Date"].dropna().unique())

    selected_date = st.selectbox("Inventory Date", dates)

    df = df[df["Date"]==selected_date]

# --------------------------------------------------
# SUMMARY
# --------------------------------------------------

    total_stock = df["Stock"].sum()
    total_value = df["Inventory Value"].sum()
    total_products = df["SKU"].nunique()

    st.subheader("📦 Inventory Summary")

    c1,c2,c3 = st.columns(3)

    c1.metric("Total SKU", total_products)
    c2.metric("Total Units", f"{total_stock:,.0f}")
    c3.metric("Inventory Value", f"₹{total_value:,.0f}")

# --------------------------------------------------
# CATEGORY SUMMARY
# --------------------------------------------------

    st.subheader("Category Summary")

    cat_summary = (
        df.groupby("Category")
        .agg({
            "Stock":"sum",
            "Inventory Value":"sum"
        })
        .reset_index()
    )

    st.dataframe(cat_summary)

# --------------------------------------------------
# PRODUCT TABLE
# --------------------------------------------------

    st.subheader("Product Inventory")

    display_cols = ["Product","SKU","Category","Stock","Cost","Inventory Value"]

    st.dataframe(df[display_cols])

# --------------------------------------------------
# DOWNLOAD
# --------------------------------------------------

    csv = df.to_csv(index=False).encode()

    st.download_button(
        "Download Inventory",
        csv,
        "inventory_snapshot.csv",
        "text/csv"
    )
