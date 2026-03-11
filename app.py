import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="Sales Dashboard", layout="wide")

st.title("📊 Sales + Revenue Dashboard")

BASE = "/mount/src/sales-dashboard"

PATHS = {
    "POS": f"{BASE}/sales_data",
    "Online": f"{BASE}/online_data"
}

REVENUE_FILE = f"{BASE}/revenue_share/revenue_share.xlsx"


# ------------------------------------------------
# LOAD SALES FILES
# ------------------------------------------------
@st.cache_data
def load_folder(folder):

    frames = []

    if not os.path.exists(folder):
        return pd.DataFrame()

    for file in os.listdir(folder):

        if file.endswith((".xlsx", ".csv")):

            path = os.path.join(folder, file)

            if file.endswith(".xlsx"):
                df = pd.read_excel(path)
            else:
                df = pd.read_csv(path)

            frames.append(df)

    if frames:
        return pd.concat(frames, ignore_index=True)

    return pd.DataFrame()


# ------------------------------------------------
# LOAD REVENUE FILE
# ------------------------------------------------
@st.cache_data
def load_revenue():

    if not os.path.exists(REVENUE_FILE):
        return pd.DataFrame()

    df = pd.read_excel(REVENUE_FILE)

    df.columns = df.columns.str.replace("\n", "")
    df.columns = df.columns.str.strip()

    df = df.rename(columns={"item": "SKU"})

    df["SKU"] = df["SKU"].astype(str).str.strip().str.upper()

    id_cols = ["SKU", "GST%"]

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

    brands = ["NIKE", "PUMA", "ADIDAS", "REEBOK", "LOTTO", "CAMPUS"]

    text = str(product).upper()

    for b in brands:
        if b in text:
            return b

    return "OTHER"


# ------------------------------------------------
# DASHBOARD SELECT
# ------------------------------------------------
mode = st.sidebar.selectbox("Dashboard", ["POS", "Online"])

df = load_folder(PATHS[mode])

if df.empty:
    st.warning("No sales data found")
    st.stop()

rev_df = load_revenue()

df.columns = df.columns.str.strip()

df["SKU"] = df["SKU"].astype(str).str.strip().str.upper()


# ------------------------------------------------
# DATE CLEANING
# ------------------------------------------------
if "Date" in df.columns:
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce", dayfirst=True)


# ------------------------------------------------
# DATE FILTER
# ------------------------------------------------
if "Date" in df.columns:

    min_date = df["Date"].min()
    max_date = df["Date"].max()

    start_date, end_date = st.sidebar.date_input(
        "Select Date Range",
        [min_date, max_date]
    )

    df = df[
        (df["Date"] >= pd.to_datetime(start_date)) &
        (df["Date"] <= pd.to_datetime(end_date))
    ]


# ------------------------------------------------
# AMOUNT CLEAN
# ------------------------------------------------
df["Amount"] = df["Amount"].astype(str).str.replace(",", "")
df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")

if "Quantity" in df.columns:
    df["Qty"] = pd.to_numeric(df["Quantity"], errors="coerce")
else:
    df["Qty"] = 1

if "Product" not in df.columns:
    df["Product"] = df["SKU"]

df["Brand"] = df["Product"].apply(detect_brand)


# ------------------------------------------------
# LOCATION FILTER
# ------------------------------------------------
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
        ["All"] + sorted(df["School Name"].unique())
    )

    if location != "All":
        df = df[df["School Name"] == location]


# ------------------------------------------------
# KPI
# ------------------------------------------------
total_qty = df["Qty"].sum()
total_sales = df["Amount"].sum()

c1, c2 = st.columns(2)

c1.metric("Units Sold", int(total_qty))
c2.metric("Sales", f"₹{total_sales:,.0f}")


# ------------------------------------------------
# REVENUE SHARE CALCULATION
# ------------------------------------------------
if location != "All" and not rev_df.empty:

    loc = location.strip().upper()

    rev_map = rev_df[rev_df["School"] == loc]

    df = df.merge(rev_map, on="SKU", how="left")

    df["RevenueShare"] = df["RevenueShare"].fillna(0)
    df["GST%"] = df["GST%"].fillna(18)

    df["Revenue_PostTax"] = df["RevenueShare"] * df["Qty"]

    df["Revenue_PreTax"] = (
        df["Revenue_PostTax"] /
        (1 + df["GST%"] / 100)
    )

    df["GST_Value"] = df["Revenue_PostTax"] - df["Revenue_PreTax"]



# ------------------------------------------------
# LOCATION REVENUE SUMMARY
# ------------------------------------------------
if location != "All":

    st.subheader(f"🏫 Revenue Summary - {location}")

    total_qty = df["Qty"].sum()
    total_sales = df["Amount"].sum()

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Total Qty", int(total_qty))
    col2.metric("Total Sales", f"₹{total_sales:,.0f}")

    if "Revenue_PostTax" in df.columns:

        col3.metric(
            "Revenue Share Post Tax",
            f"₹{df['Revenue_PostTax'].sum():,.0f}"
        )

        col4.metric(
            "Revenue Share Pre Tax",
            f"₹{df['Revenue_PreTax'].sum():,.0f}"
        )




# ------------------------------------------------
# PRODUCT SALES SUMMARY
# ------------------------------------------------
st.subheader("📦 Product Sales Summary")

group_cols = {
    "Qty_Sold": ("Qty", "sum"),
    "Sales_Value": ("Amount", "sum")
}

if "Revenue_PostTax" in df.columns:
    group_cols["Revenue_PostTax"] = ("Revenue_PostTax", "sum")

if "Revenue_PreTax" in df.columns:
    group_cols["Revenue_PreTax"] = ("Revenue_PreTax", "sum")

product_summary = (
    df.groupby(["SKU", "Product"])
    .agg(**group_cols)
    .reset_index()
    .sort_values("Sales_Value", ascending=False)
)

st.dataframe(product_summary, use_container_width=True)


# ------------------------------------------------
# DOWNLOAD PRODUCT SUMMARY
# ------------------------------------------------
csv = product_summary.to_csv(index=False).encode("utf-8")

st.download_button(
    "⬇ Download Product Summary",
    csv,
    "product_sales_summary.csv",
    "text/csv"
)

# ------------------------------------------------
# TOP PRODUCTS
# ------------------------------------------------
st.subheader("🏆 Top Products")

top_products = (
    df.groupby("Product")
    .agg(Qty=("Qty", "sum"), Sales=("Amount", "sum"))
    .reset_index()
    .sort_values("Sales", ascending=False)
    .head(20)
)

st.dataframe(top_products)


# ------------------------------------------------
# BRAND PERFORMANCE
# ------------------------------------------------
st.subheader("🏷 Brand Performance")

brand_perf = (
    df.groupby("Brand")
    .agg(Qty=("Qty", "sum"), Sales=("Amount", "sum"))
    .reset_index()
    .sort_values("Sales", ascending=False)
)

st.dataframe(brand_perf)
