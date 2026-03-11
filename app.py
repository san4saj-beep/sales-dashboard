import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="Unified Sales Dashboard", layout="wide")

st.title("📊 Sales + Revenue Dashboard")

BASE = "/mount/src/sales-dashboard"

PATHS = {
    "POS": f"{BASE}/sales_data",
    "Online": f"{BASE}/online_data",
    "B2B": f"{BASE}/B2B",
    "Inventory": f"{BASE}/inventory"
}

REVENUE_FILE = f"{BASE}/revenue_share/revenue_share.xlsx"


# ------------------------------------------------
# LOAD DATA
# ------------------------------------------------

@st.cache_data
def load_folder(folder):

    frames = []

    if not os.path.exists(folder):
        return pd.DataFrame()

    for file in os.listdir(folder):

        if file.endswith((".xlsx",".csv")):

            path = os.path.join(folder,file)

            try:

                if file.endswith(".xlsx"):
                    df = pd.read_excel(path)
                else:
                    df = pd.read_csv(path)

                frames.append(df)

            except:
                pass

    if frames:
        return pd.concat(frames,ignore_index=True)

    return pd.DataFrame()


# ------------------------------------------------
# LOAD REVENUE
# ------------------------------------------------

@st.cache_data
def load_revenue():

    if not os.path.exists(REVENUE_FILE):
        return pd.DataFrame()

    df = pd.read_excel(REVENUE_FILE)

    df.columns = df.columns.str.replace("\n","")
    df.columns = df.columns.str.strip()

    df = df.rename(columns={"item":"SKU"})

    df["SKU"] = df["SKU"].astype(str).str.strip().str.upper()

    id_cols = ["SKU","GST%"]

    school_cols = [c for c in df.columns if c not in id_cols]

    rev_long = df.melt(
        id_vars=id_cols,
        value_vars=school_cols,
        var_name="School",
        value_name="RevenueShare"
    )

    rev_long["School"] = rev_long["School"].astype(str).str.strip().str.upper()

    rev_long = rev_long.dropna(subset=["RevenueShare"])

    return rev_long


# ------------------------------------------------
# BRAND DETECTION
# ------------------------------------------------

def detect_brand(product):

    brands = ["NIKE","PUMA","ADIDAS","REEBOK","LOTTO","CAMPUS"]

    p = str(product).upper()

    for b in brands:
        if b in p:
            return b

    return "OTHER"


# ------------------------------------------------
# DASHBOARD SELECT
# ------------------------------------------------

mode = st.sidebar.selectbox(
    "Dashboard",
    ["POS","Online","B2B","Inventory"]
)

df = load_folder(PATHS[mode])

if df.empty:
    st.warning("No data available")
    st.stop()

df.columns = df.columns.str.strip()

rev_df = load_revenue()


# =================================================
# SALES DASHBOARD
# =================================================

if mode in ["POS","Online"]:

    df["SKU"] = df["SKU"].astype(str).str.strip().str.upper()

    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"],errors="coerce",dayfirst=True)

    if "Amount" in df.columns:
        df["Amount"] = (
            df["Amount"]
            .astype(str)
            .str.replace(",","")
        )

        df["Amount"] = pd.to_numeric(df["Amount"],errors="coerce")

    if "Quantity" in df.columns:
        df["Qty"] = pd.to_numeric(df["Quantity"],errors="coerce")
    else:
        df["Qty"] = 1

    if "Product" not in df.columns:
        df["Product"] = df["SKU"]

    df["Brand"] = df["Product"].apply(detect_brand)


    # ----------------------------------------------
    # LOCATION FILTER
    # ----------------------------------------------

    location = "All"

    if mode == "POS":

        location = st.sidebar.selectbox(
            "Store",
            ["All"] + sorted(df["Store"].dropna().unique())
        )

        if location != "All":
            df = df[df["Store"] == location]


    if mode == "Online":

        df["School Name"] = df["School Name"].astype(str).str.strip().str.upper()

        location = st.sidebar.selectbox(
            "School",
            ["All"] + sorted(df["School Name"].dropna().unique())
        )

        if location != "All":
            df = df[df["School Name"] == location]


    # ----------------------------------------------
    # DATE FILTER
    # ----------------------------------------------

    if "Date" in df.columns:

        min_d = df["Date"].min().date()
        max_d = df["Date"].max().date()

        dr = st.sidebar.date_input(
            "Date Range",
            [min_d,max_d]
        )

        if len(dr)==2:

            start,end = dr

            df = df[
                (df["Date"].dt.date>=start) &
                (df["Date"].dt.date<=end)
            ]


    # ----------------------------------------------
    # KPI
    # ----------------------------------------------

    total_qty = df["Qty"].sum()
    total_sales = df["Amount"].sum()

    c1,c2 = st.columns(2)

    c1.metric("Units Sold",f"{int(total_qty):,}")
    c2.metric("Sales",f"₹{total_sales:,.0f}")


    # ----------------------------------------------
    # PRODUCT SEARCH
    # ----------------------------------------------

    st.subheader("🔎 Product Search")

    search = st.text_input("Search SKU or Product")

    if search:

        s_df = df[
            df["SKU"].str.contains(search,case=False,na=False) |
            df["Product"].str.contains(search,case=False,na=False)
        ]

        qty = s_df["Qty"].sum()
        sales = s_df["Amount"].sum()

        sc1,sc2 = st.columns(2)

        sc1.metric("Total Qty Sold",int(qty))
        sc2.metric("Total Sales",f"₹{sales:,.0f}")

        st.dataframe(s_df)


    # ----------------------------------------------
    # REVENUE SHARE
    # ----------------------------------------------

    if location!="All" and not rev_df.empty:

        loc = location.strip().upper()

        rev_map = rev_df[rev_df["School"]==loc]

        df = df.merge(rev_map,on="SKU",how="left")

        df["RevenueShare"] = df["RevenueShare"].fillna(0)

        df["GST%"] = df["GST%"].fillna(18)

        df["Revenue_PostTax"] = df["RevenueShare"] * df["Qty"]

        df["Revenue_PreTax"] = (
            df["Revenue_PostTax"] /
            (1 + df["GST%"]/100)
        ).round(2)

        df["GST_Value"] = df["Revenue_PostTax"] - df["Revenue_PreTax"]

        st.subheader("🏫 Revenue Share")

        pretax = df["Revenue_PreTax"].sum()
        gst = df["GST_Value"].sum()
        posttax = df["Revenue_PostTax"].sum()

        r1,r2,r3 = st.columns(3)

        r1.metric("Revenue PreTax",f"₹{pretax:,.0f}")
        r2.metric("GST",f"₹{gst:,.0f}")
        r3.metric("Revenue PostTax",f"₹{posttax:,.0f}")


    # ----------------------------------------------
    # TOP PRODUCTS
    # ----------------------------------------------

    st.subheader("Top Products")

    top = (
        df.groupby("Product")
        .agg(Qty=("Qty","sum"),Sales=("Amount","sum"))
        .reset_index()
        .sort_values("Sales",ascending=False)
        .head(20)
    )

    st.dataframe(top)


    # ----------------------------------------------
    # BRAND PERFORMANCE
    # ----------------------------------------------

    st.subheader("Brand Performance")

    brand = (
        df.groupby("Brand")
        .agg(Qty=("Qty","sum"),Sales=("Amount","sum"))
        .reset_index()
        .sort_values("Sales",ascending=False)
    )

    st.dataframe(brand)

# ----------------------------------------------
# PRODUCT SALES SUMMARY (ITEM LEVEL)
# ----------------------------------------------

st.subheader("📦 Product Sales Summary")

product_summary = (
    df.groupby(["SKU","Product"])
    .agg(
        Qty_Sold=("Qty","sum"),
        Sales_Value=("Amount","sum"),
        Revenue_PostTax=("Revenue_PostTax","sum"),
        Revenue_PreTax=("Revenue_PreTax","sum"),
        GST_Value=("GST_Value","sum")
    )
    .reset_index()
    .sort_values("Sales_Value",ascending=False)
)

st.dataframe(product_summary,use_container_width=True)


# ----------------------------------------------
# DOWNLOAD OPTION
# ----------------------------------------------

csv = product_summary.to_csv(index=False).encode("utf-8")

st.download_button(
    label="⬇ Download Product Summary",
    data=csv,
    file_name="product_sales_summary.csv",
    mime="text/csv"
)
# =================================================
# INVENTORY
# =================================================

elif mode=="Inventory":

    st.subheader("Inventory Data")

    st.dataframe(df)


# =================================================
# B2B
# =================================================

elif mode=="B2B":

    if "Value" in df.columns:

        df["Value"] = (
            df["Value"]
            .astype(str)
            .str.replace(",","")
        )

        df["Value"] = pd.to_numeric(df["Value"],errors="coerce")

        total = df["Value"].sum()

        st.metric("Total B2B Sales",f"₹{total:,.0f}")

    st.dataframe(df)
