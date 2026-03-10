import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="Sales Dashboard V3", layout="wide")

st.title("📊 Unified Sales Dashboard")

BASE_PATH = "/mount/src/sales-dashboard"

PATHS = {
    "POS": f"{BASE_PATH}/sales_data",
    "Online": f"{BASE_PATH}/online_data",
    "B2B": f"{BASE_PATH}/B2B",
    "Inventory": f"{BASE_PATH}/inventory"
}

# ---------------------------------------------------
# LOAD DATA
# ---------------------------------------------------

@st.cache_data
def load_folder(folder):

    if not os.path.exists(folder):
        return pd.DataFrame()

    files = [f for f in os.listdir(folder) if f.endswith((".xlsx",".csv"))]

    frames = []

    for f in files:

        path = os.path.join(folder,f)

        try:

            if f.endswith(".xlsx"):
                df = pd.read_excel(path)
            else:
                df = pd.read_csv(path)

            df["SourceFile"] = f
            frames.append(df)

        except:
            pass

    if frames:
        return pd.concat(frames,ignore_index=True)

    return pd.DataFrame()


# ---------------------------------------------------
# DASHBOARD SELECT
# ---------------------------------------------------

mode = st.sidebar.selectbox(
    "Select Dashboard",
    ["POS","Online","B2B","Inventory"]
)

df = load_folder(PATHS[mode])

if df.empty:
    st.warning("No data found")
    st.stop()

df.columns = df.columns.str.strip()

# ===================================================
# POS + ONLINE SALES
# ===================================================

if mode in ["POS","Online"]:

    # ------------------------------
    # DATE HANDLING
    # ------------------------------

    if mode == "Online":

        df["Date"] = pd.to_datetime(
            df["Date"],
            format="%d-%m-%Y %H:%M",
            errors="coerce"
        )

    else:

        df["Date"] = pd.to_datetime(
            df["Date"],
            format="%d-%m-%Y",
            errors="coerce"
        )

    df = df.dropna(subset=["Date"])

    if df.empty:
        st.error("No valid dates found")
        st.stop()

    # ------------------------------
    # AMOUNT
    # ------------------------------

    if "Amount" in df.columns:

        df["Amount"] = (
            df["Amount"]
            .astype(str)
            .str.replace(",","")
        )

        df["Amount"] = pd.to_numeric(df["Amount"],errors="coerce")

    else:
        df["Amount"] = 0

    # ------------------------------
    # QUANTITY
    # ------------------------------

    if mode == "Online":
        df["Qty"] = 1
    else:
        if "Quantity" in df.columns:
            df["Qty"] = pd.to_numeric(df["Quantity"],errors="coerce")
        else:
            df["Qty"] = 1

    # ------------------------------
    # CLEAN PRODUCT COLUMN
    # ------------------------------

    if "Product" in df.columns:
        df["Product"] = df["Product"].astype(str)

    # ------------------------------
    # STORE FILTER
    # ------------------------------

    if "Store" in df.columns:

        store = st.sidebar.selectbox(
            "Store",
            ["All"] + sorted(df["Store"].dropna().unique())
        )

        if store != "All":
            df = df[df["Store"] == store]

    # ------------------------------
    # DATE FILTER
    # ------------------------------

    min_date = df["Date"].min().date()
    max_date = df["Date"].max().date()

    date_range = st.sidebar.date_input(
        "Date Range",
        value=[min_date,max_date]
    )

    if len(date_range) == 2:
        start,end = date_range
    else:
        start,end = min_date,max_date

    df = df[
        (df["Date"].dt.date >= start) &
        (df["Date"].dt.date <= end)
    ]

    # ===================================================
    # KPI SUMMARY
    # ===================================================

    total_qty = df["Qty"].sum()
    total_sales = df["Amount"].sum()

    c1,c2 = st.columns(2)

    c1.metric("Total Quantity Sold",f"{int(total_qty):,}")
    c2.metric("Total Sales",f"₹{total_sales:,.0f}")

    # ===================================================
    # PRODUCT SEARCH
    # ===================================================

    if "Product" in df.columns:

        st.subheader("🔎 Product Search")

        search = st.text_input("Search product")

        if search:

            result = df[
                df["Product"].str.contains(search,case=False,na=False)
            ]

            if not result.empty:

                summary = (
                    result.groupby("Product")
                    .agg(
                        Qty=("Qty","sum"),
                        Sales=("Amount","sum")
                    )
                    .reset_index()
                    .sort_values("Sales",ascending=False)
                )

                st.dataframe(summary,use_container_width=True)

            else:
                st.info("No products found")

    # ===================================================
    # TOP PRODUCTS
    # ===================================================

    if "Product" in df.columns:

        st.subheader("🏆 Top Selling Products")

        top_products = (
            df.groupby("Product")
            .agg(
                Qty=("Qty","sum"),
                Sales=("Amount","sum")
            )
            .reset_index()
            .sort_values("Sales",ascending=False)
            .head(20)
        )

        st.dataframe(top_products,use_container_width=True)

    # ===================================================
    # BRAND PERFORMANCE
    # ===================================================

    if "Brand" in df.columns:

        st.subheader("👟 Brand Performance")

        brand = (
            df.groupby("Brand")
            .agg(
                Qty=("Qty","sum"),
                Sales=("Amount","sum")
            )
            .reset_index()
            .sort_values("Sales",ascending=False)
        )

        st.dataframe(brand,use_container_width=True)

    # ===================================================
    # STORE PERFORMANCE
    # ===================================================

    if "Store" in df.columns:

        st.subheader("🏪 Store Performance")

        store_perf = (
            df.groupby("Store")
            .agg(
                Qty=("Qty","sum"),
                Sales=("Amount","sum")
            )
            .reset_index()
            .sort_values("Sales",ascending=False)
        )

        st.dataframe(store_perf,use_container_width=True)

# ===================================================
# B2B
# ===================================================

elif mode == "B2B":

    df["Voucher No."] = df["Voucher No."].ffill()
    df["Particulars"] = df["Particulars"].ffill()

    df["Value"] = (
        df["Value"]
        .astype(str)
        .str.replace(",","")
        .str.replace("Dr","")
        .str.replace("Cr","")
    )

    df["Value"] = pd.to_numeric(df["Value"],errors="coerce")

    df["Date"] = pd.to_datetime(df["Date"],errors="coerce")

    summary = (
        df.groupby(["Voucher No.","Particulars","Date"])
        .agg(Value=("Value","sum"))
        .reset_index()
    )

    c1,c2 = st.columns(2)

    c1.metric("Invoices",summary["Voucher No."].nunique())
    c2.metric("Total Sales",f"₹{summary['Value'].sum():,.0f}")

    st.dataframe(summary.sort_values("Date",ascending=False))

# ===================================================
# INVENTORY
# ===================================================

elif mode == "Inventory":

    df["Date"] = pd.to_datetime(df["Date"],errors="coerce")

    total_units = df["Inventory"].sum()
    stock_value = (df["Inventory"] * df["Cost Price"]).sum()

    c1,c2 = st.columns(2)

    c1.metric("Total Units",f"{int(total_units):,}")
    c2.metric("Stock Value",f"₹{stock_value:,.0f}")

    st.dataframe(
        df[["Date","Product","SKU","Inventory","Cost Price"]],
        use_container_width=True
    )
