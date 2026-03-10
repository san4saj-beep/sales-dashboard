import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="Business Dashboard", layout="wide")

st.title("📊 Sales & Inventory Dashboard")

BASE_PATH = "/mount/src/sales-dashboard"

PATHS = {
    "POS": f"{BASE_PATH}/sales_data",
    "Online": f"{BASE_PATH}/online_data",
    "B2B": f"{BASE_PATH}/B2B",
    "Inventory": f"{BASE_PATH}/inventory",
}

# -------------------------------------------------------
# LOAD FILES
# -------------------------------------------------------

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


# -------------------------------------------------------
# SELECT DASHBOARD
# -------------------------------------------------------

mode = st.sidebar.selectbox(
    "Dashboard",
    ["POS","Online","B2B","Inventory"]
)

df = load_folder(PATHS[mode])

if df.empty:
    st.warning("No data found")
    st.stop()

df.columns = df.columns.str.strip()


# ======================================================
# POS + ONLINE SALES
# ======================================================

if mode in ["POS","Online"]:

    # ---------------------------------------------------
    # DATE
    # ---------------------------------------------------

    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(
            df["Date"],
            format="%d-%m-%Y %H:%M",
            errors="coerce"
        )
        date_col = "Date"

    elif "Created" in df.columns:
        df["Created"] = pd.to_datetime(df["Created"],errors="coerce")
        date_col = "Created"

    else:
        st.error("Date column not found")
        st.stop()

    # ---------------------------------------------------
    # AMOUNT
    # ---------------------------------------------------

    if "Amount" in df.columns:
        df["Amount"] = pd.to_numeric(df["Amount"],errors="coerce")
    else:
        df["Amount"] = 0

    # ---------------------------------------------------
    # QUANTITY
    # ---------------------------------------------------

    if mode == "Online":

        # each row = 1 item
        df["Qty"] = 1

    else:

        if "Quantity" in df.columns:
            df["Qty"] = pd.to_numeric(df["Quantity"],errors="coerce")
        else:
            df["Qty"] = 1

    # ---------------------------------------------------
    # STORE
    # ---------------------------------------------------

    if "Store" in df.columns:

        store = st.sidebar.selectbox(
            "Store",
            ["All"] + sorted(df["Store"].dropna().unique())
        )

        if store != "All":
            df = df[df["Store"]==store]

    # ---------------------------------------------------
    # DATE FILTER
    # ---------------------------------------------------

    start,end = st.sidebar.date_input(
        "Date Range",
        [df[date_col].min(),df[date_col].max()]
    )

    df = df[
        (df[date_col].dt.date >= start) &
        (df[date_col].dt.date <= end)
    ]

    # ---------------------------------------------------
    # SUMMARY
    # ---------------------------------------------------

    total_qty = df["Qty"].sum()
    total_sales = df["Amount"].sum()

    c1,c2 = st.columns(2)

    c1.metric("Total Quantity",f"{int(total_qty):,}")
    c2.metric("Total Sales",f"₹{total_sales:,.0f}")

    # ---------------------------------------------------
    # PRODUCT SALES
    # ---------------------------------------------------

    if "Product" in df.columns:

        st.subheader("Top Products")

        prod = (
            df.groupby("Product")
            .agg(
                Qty=("Qty","sum"),
                Sales=("Amount","sum")
            )
            .reset_index()
            .sort_values("Sales",ascending=False)
            .head(20)
        )

        st.dataframe(prod,use_container_width=True)

    # ---------------------------------------------------
    # STORE SALES
    # ---------------------------------------------------

    if "Store" in df.columns:

        st.subheader("Store Sales")

        store_sales = (
            df.groupby("Store")["Amount"]
            .sum()
            .reset_index()
            .sort_values("Amount",ascending=False)
        )

        st.dataframe(store_sales,use_container_width=True)



# ======================================================
# B2B
# ======================================================

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
    c2.metric("Sales",f"₹{summary['Value'].sum():,.0f}")

    st.dataframe(summary.sort_values("Date",ascending=False),use_container_width=True)


# ======================================================
# INVENTORY
# ======================================================

elif mode == "Inventory":

    df["Date"] = pd.to_datetime(df["Date"],errors="coerce")

    if "Category" in df.columns:

        cat = st.sidebar.selectbox(
            "Category",
            ["All"] + sorted(df["Category"].dropna().unique())
        )

        if cat != "All":
            df = df[df["Category"]==cat]

    start,end = st.sidebar.date_input(
        "Date Range",
        [df["Date"].min(),df["Date"].max()]
    )

    df = df[
        (df["Date"].dt.date>=start) &
        (df["Date"].dt.date<=end)
    ]

    total_units = df["Inventory"].sum()
    stock_value = (df["Inventory"]*df["Cost Price"]).sum()

    c1,c2 = st.columns(2)

    c1.metric("Total Units",f"{int(total_units):,}")
    c2.metric("Stock Value",f"₹{stock_value:,.0f}")

    st.dataframe(
        df[["Date","Product","SKU","Inventory","Cost Price"]],
        use_container_width=True
    )
