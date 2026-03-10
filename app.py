import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="Unified Business Dashboard", layout="wide")

st.title("📊 Unified Sales & Inventory Dashboard")

# -------------------------------------------------------
# DASHBOARD SELECT
# -------------------------------------------------------

data_source = st.sidebar.selectbox(
    "Select Dashboard",
    ["POS", "Online", "B2B", "Inventory"]
)

# -------------------------------------------------------
# BASE PATH
# -------------------------------------------------------

base_path = "/mount/src/sales-dashboard"

folders = {
    "POS": os.path.join(base_path, "sales_data"),
    "Online": os.path.join(base_path, "online_data"),
    "B2B": os.path.join(base_path, "B2B"),
    "Inventory": os.path.join(base_path, "inventory"),
}

folder_path = folders[data_source]

# -------------------------------------------------------
# FILE LOADER
# -------------------------------------------------------

def load_data_from_folder(folder):

    if not os.path.exists(folder):
        return pd.DataFrame()

    files = [
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if f.endswith((".xlsx", ".csv"))
    ]

    dfs = []

    for file in files:

        try:

            if file.endswith(".xlsx"):
                df = pd.read_excel(file)
            else:
                df = pd.read_csv(file)

            df["SourceFile"] = os.path.basename(file)

            dfs.append(df)

        except Exception as e:
            st.warning(f"Could not read {file}: {e}")

    if dfs:
        return pd.concat(dfs, ignore_index=True)

    return pd.DataFrame()


# =====================================================
# POS + ONLINE DASHBOARD
# =====================================================

if data_source in ["POS", "Online"]:

    df = load_data_from_folder(folder_path)

    if df.empty:
        st.warning("No data found")
        st.stop()

    df.columns = df.columns.str.strip()

# -----------------------------------------------------
# DATE COLUMN FIX
# -----------------------------------------------------

    date_col = None

    if "Date" in df.columns:
        date_col = "Date"

    elif "Created" in df.columns:
        date_col = "Created"

    elif "Invoice Created" in df.columns:
        date_col = "Invoice Created"

    if date_col:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")

# -----------------------------------------------------
# AMOUNT CLEAN
# -----------------------------------------------------

    if "Amount" in df.columns:

        df["Amount"] = (
            df["Amount"]
            .astype(str)
            .str.replace(",", "")
        )

        df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")

# -----------------------------------------------------
# ONLINE SALES FIX
# -----------------------------------------------------

    if data_source == "Online":

        # keep only forward order statuses
        if "Sale Order Item Status" in df.columns:

            df = df[
                df["Sale Order Item Status"].str.contains(
                    "FULFILLABLE|DELIVERED|SHIPPED|PROCESSING",
                    case=False,
                    na=False
                )
            ]

        # quantity = unique item codes
        if "Sale Order Item Code" in df.columns:
            qty_col = "Sale Order Item Code"
        else:
            df["Quantity"] = 1
            qty_col = "Quantity"

    else:

        if "Quantity" in df.columns:
            df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce")
            qty_col = "Quantity"

        else:
            df["Quantity"] = 1
            qty_col = "Quantity"

# -----------------------------------------------------
# STORE FILTER
# -----------------------------------------------------

    if "Store" in df.columns:

        store_filter = st.sidebar.selectbox(
            "Store",
            ["All"] + sorted(df["Store"].dropna().unique())
        )

    else:
        store_filter = "All"

# -----------------------------------------------------
# DATE FILTER
# -----------------------------------------------------

    filtered_df = df.copy()

    if date_col:

        date_min = df[date_col].min()
        date_max = df[date_col].max()

        date_range = st.sidebar.date_input(
            "Date Range",
            [date_min, date_max]
        )

        if len(date_range) == 2:

            start, end = date_range

            filtered_df = filtered_df[
                (filtered_df[date_col].dt.date >= start) &
                (filtered_df[date_col].dt.date <= end)
            ]

    if store_filter != "All":
        filtered_df = filtered_df[filtered_df["Store"] == store_filter]

# -----------------------------------------------------
# SUMMARY
# -----------------------------------------------------

    if data_source == "Online" and "Sale Order Item Code" in filtered_df.columns:
        total_qty = filtered_df["Sale Order Item Code"].nunique()
    else:
        total_qty = filtered_df[qty_col].sum()

    total_sales = filtered_df["Amount"].sum()

    st.subheader("Overall Summary")

    c1, c2 = st.columns(2)

    c1.metric("Total Qty Sold", f"{int(total_qty):,}")
    c2.metric("Total Sales", f"₹{total_sales:,.0f}")

# -----------------------------------------------------
# STORE SALES
# -----------------------------------------------------

    if "Store" in filtered_df.columns:

        st.subheader("Store Sales")

        store_summary = (
            filtered_df
            .groupby("Store")["Amount"]
            .sum()
            .reset_index()
            .sort_values("Amount", ascending=False)
        )

        st.dataframe(store_summary, use_container_width=True)

# -----------------------------------------------------
# PRODUCT SALES
# -----------------------------------------------------

    if "Product" in filtered_df.columns:

        st.subheader("Product Sales")

        if data_source == "Online" and "Sale Order Item Code" in filtered_df.columns:

            product_summary = (
                filtered_df
                .groupby("Product")
                .agg(
                    Qty=("Sale Order Item Code", "nunique"),
                    Sales=("Amount", "sum")
                )
                .reset_index()
                .sort_values("Sales", ascending=False)
            )

        else:

            product_summary = (
                filtered_df
                .groupby("Product")
                .agg(
                    Qty=(qty_col, "sum"),
                    Sales=("Amount", "sum")
                )
                .reset_index()
                .sort_values("Sales", ascending=False)
            )

        st.dataframe(product_summary, use_container_width=True)


# =====================================================
# B2B DASHBOARD
# =====================================================

elif data_source == "B2B":

    raw = load_data_from_folder(folder_path)

    if raw.empty:
        st.warning("No B2B data found")
        st.stop()

    raw.columns = raw.columns.str.strip()

    raw["Voucher No."] = raw["Voucher No."].ffill()
    raw["Particulars"] = raw["Particulars"].ffill()

    raw["Date"] = pd.to_datetime(raw["Date"], errors="coerce")

    raw["Value"] = (
        raw["Value"]
        .astype(str)
        .str.replace(",", "")
        .str.replace("Dr", "")
        .str.replace("Cr", "")
    )

    raw["Value"] = pd.to_numeric(raw["Value"], errors="coerce")

    invoice_summary = (
        raw.groupby(["Voucher No.", "Particulars", "Date"])
        .agg(Value=("Value", "sum"))
        .reset_index()
        .rename(columns={
            "Particulars": "Vendor",
            "Value": "Invoice Value"
        })
    )

    st.subheader("B2B Sales Summary")

    c1, c2 = st.columns(2)

    c1.metric("Total Invoices", invoice_summary["Voucher No."].nunique())
    c2.metric("Total Sales", f"₹{invoice_summary['Invoice Value'].sum():,.0f}")

    st.dataframe(invoice_summary.sort_values("Date", ascending=False))


# =====================================================
# INVENTORY DASHBOARD
# =====================================================

elif data_source == "Inventory":

    df = load_data_from_folder(folder_path)

    if df.empty:
        st.warning("No inventory files found")
        st.stop()

    df.columns = df.columns.str.strip()

    required_cols = ["Product", "SKU", "Inventory", "Cost Price", "Date"]

    for col in required_cols:
        if col not in df.columns:
            st.error(f"Missing column: {col}")
            st.stop()

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

# CATEGORY FILTER

    if "Category" in df.columns:

        category = st.sidebar.selectbox(
            "Category",
            ["All"] + sorted(df["Category"].dropna().unique())
        )

        if category != "All":
            df = df[df["Category"] == category]

# DATE FILTER

    date_min = df["Date"].min()
    date_max = df["Date"].max()

    date_range = st.sidebar.date_input(
        "Inventory Date Range",
        [date_min, date_max]
    )

    if len(date_range) == 2:

        start, end = date_range

        df = df[
            (df["Date"].dt.date >= start) &
            (df["Date"].dt.date <= end)
        ]

# SUMMARY

    total_stock = df["Inventory"].sum()
    stock_value = (df["Inventory"] * df["Cost Price"]).sum()

    st.subheader("Inventory Summary")

    c1, c2 = st.columns(2)

    c1.metric("Total Units", f"{int(total_stock):,}")
    c2.metric("Stock Value", f"₹{stock_value:,.0f}")

    st.subheader("Inventory Details")

    st.dataframe(
        df[["Date", "Product", "SKU", "Inventory", "Cost Price"]],
        use_container_width=True
    )
