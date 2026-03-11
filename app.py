import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="Retail Dashboard", layout="wide")

st.title("📊 Unified Retail Dashboard")

BASE_PATH = "/mount/src/sales-dashboard"

PATHS = {
    "POS": f"{BASE_PATH}/sales_data",
    "Online": f"{BASE_PATH}/online_data",
    "B2B": f"{BASE_PATH}/B2B",
    "Inventory": f"{BASE_PATH}/inventory"
}

REV_PATH = f"{BASE_PATH}/revenue_share/revenue_share.xlsx"

# ---------------------------------------------------
# LOAD SALES FILES
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

            frames.append(df)

        except:
            pass

    if frames:
        return pd.concat(frames,ignore_index=True)

    return pd.DataFrame()

# ---------------------------------------------------
# LOAD REVENUE SHARE
# ---------------------------------------------------

@st.cache_data
def load_revenue():

    if not os.path.exists(REV_PATH):
        return pd.DataFrame()

    df = pd.read_excel(REV_PATH)

    df.columns = df.columns.str.strip()

    df = df.rename(columns={"item":"SKU","item\n":"SKU"})

    return df

# ---------------------------------------------------
# BRAND DETECTION
# ---------------------------------------------------

def detect_brand(product):

    brands = ["NIKE","PUMA","ADIDAS","REEBOK","LOTTO","CAMPUS"]

    product = str(product).upper()

    for b in brands:
        if b in product:
            return b

    return "OTHER"

# ---------------------------------------------------
# DASHBOARD SELECT
# ---------------------------------------------------

mode = st.sidebar.selectbox(
    "Dashboard",
    ["POS","Online","B2B","Inventory"]
)

df = load_folder(PATHS[mode])

if df.empty:
    st.warning("No data found")
    st.stop()

df.columns = df.columns.str.strip()

rev_df = load_revenue()

# ===================================================
# POS + ONLINE SALES
# ===================================================

if mode in ["POS","Online"]:

    df["Date"] = pd.to_datetime(df["Date"],errors="coerce",dayfirst=True)

    df = df.dropna(subset=["Date"])

    # Amount cleaning
    if "Amount" in df.columns:

        df["Amount"] = (
            df["Amount"]
            .astype(str)
            .str.replace(",","")
        )

        df["Amount"] = pd.to_numeric(df["Amount"],errors="coerce")

    else:
        df["Amount"] = 0

    # Quantity
    if mode == "Online":
        df["Qty"] = 1
    else:
        if "Quantity" in df.columns:
            df["Qty"] = pd.to_numeric(df["Quantity"],errors="coerce")
        else:
            df["Qty"] = 1

    # Product cleaning
    if "Product" in df.columns:

        df["Product"] = df["Product"].astype(str)
        df["Brand"] = df["Product"].apply(detect_brand)

    # ---------------------------------------
    # STORE / SCHOOL FILTER
    # ---------------------------------------

    location = "All"

    if mode == "POS" and "Store" in df.columns:

        location = st.sidebar.selectbox(
            "Store",
            ["All"] + sorted(df["Store"].dropna().unique())
        )

        if location != "All":
            df = df[df["Store"] == location]

    if mode == "Online" and "School Name" in df.columns:

        location = st.sidebar.selectbox(
            "School",
            ["All"] + sorted(df["School Name"].dropna().unique())
        )

        if location != "All":
            df = df[df["School Name"] == location]

    # ---------------------------------------
    # DATE FILTER
    # ---------------------------------------

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

    # ---------------------------------------
    # SALES KPI
    # ---------------------------------------

    total_qty = df["Qty"].sum()
    total_sales = df["Amount"].sum()

    c1,c2 = st.columns(2)

    c1.metric("Units Sold",f"{int(total_qty):,}")
    c2.metric("Sales",f"₹{total_sales:,.0f}")

    # ===================================================
    # REVENUE SHARE CALCULATION
    # ===================================================

    if not rev_df.empty and "SKU" in df.columns and location != "All":

        if location in rev_df.columns:

            revenue_map = rev_df[["SKU",location,"GST%"]]

            revenue_map = revenue_map.rename(
                columns={location:"RevenueShare"}
            )

            df = df.merge(revenue_map,on="SKU",how="left")

            df["RevenueShare"] = df["RevenueShare"].fillna(0)

            df["GST%"] = df["GST%"].fillna(18)

            # Post tax (sheet values include GST)
            df["Revenue_PostTax"] = df["RevenueShare"] * df["Qty"]

            # Pre tax calculation using GST column
            df["Revenue_PreTax"] = (
                df["Revenue_PostTax"] /
                (1 + df["GST%"]/100)
            ).round(2)

            df["GST_Value"] = df["Revenue_PostTax"] - df["Revenue_PreTax"]

            st.subheader("🏫 School Revenue Share")

            pretax = df["Revenue_PreTax"].sum()
            posttax = df["Revenue_PostTax"].sum()
            gstval = df["GST_Value"].sum()

            c1,c2,c3 = st.columns(3)

            c1.metric("Revenue Pre Tax",f"₹{pretax:,.0f}")
            c2.metric("GST",f"₹{gstval:,.0f}")
            c3.metric("Revenue Post Tax",f"₹{posttax:,.0f}")

            item_rev = (
                df.groupby(["Product","SKU"])
                .agg(
                    Qty=("Qty","sum"),
                    PreTax=("Revenue_PreTax","sum"),
                    GST=("GST_Value","sum"),
                    PostTax=("Revenue_PostTax","sum")
                )
                .reset_index()
                .sort_values("PostTax",ascending=False)
            )

            st.subheader("Revenue Share by Item")

            st.dataframe(item_rev,use_container_width=True)

    # ===================================================
    # BRAND PERFORMANCE
    # ===================================================

    st.subheader("Brand Performance")

    brand_perf = (
        df.groupby("Brand")
        .agg(
            Qty=("Qty","sum"),
            Sales=("Amount","sum")
        )
        .reset_index()
        .sort_values("Sales",ascending=False)
    )

    st.dataframe(brand_perf,use_container_width=True)

# ===================================================
# B2B
# ===================================================

elif mode == "B2B":

    df["Date"] = pd.to_datetime(df["Date"],errors="coerce")

    df["Value"] = (
        df["Value"]
        .astype(str)
        .str.replace(",","")
        .str.replace("Dr","")
        .str.replace("Cr","")
    )

    df["Value"] = pd.to_numeric(df["Value"],errors="coerce")

    total_sales = df["Value"].sum()

    st.metric("Total B2B Sales",f"₹{total_sales:,.0f}")

    st.dataframe(df)

# ===================================================
# INVENTORY
# ===================================================

elif mode == "Inventory":

    total_units = df["Inventory"].sum()

    stock_value = (df["Inventory"] * df["Cost Price"]).sum()

    c1,c2 = st.columns(2)

    c1.metric("Total Units",f"{int(total_units):,}")
    c2.metric("Stock Value",f"₹{stock_value:,.0f}")

    st.dataframe(df)
