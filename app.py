import streamlit as st
import pandas as pd
import os
from io import BytesIO

# --- Page Setup ---
st.set_page_config(page_title="Sales Dashboard", layout="wide")
st.title("📊 Unified Sales Dashboard")

# --- Folder Paths ---
data_folders = {
    "POS": "sales_data",      # POS sales data
    "Online": "online_data"   # Online sales data
}

# --- Dropdown to Choose Source ---
selected_source = st.sidebar.selectbox("Select Data Source", options=list(data_folders.keys()))
folder_path = data_folders[selected_source]

# --- Safe Loader Function ---
def load_data_from_folder(folder):
    all_data = []

    for file in os.listdir(folder):
        if file.endswith(".csv"):
            path = os.path.join(folder, file)
            df = pd.read_csv(path)

            # --- Clean duplicate or messy columns ---
            df.columns = df.columns.astype(str).str.strip()
            df = df.loc[:, ~df.columns.duplicated()]
            df.columns = [c.strip().title() for c in df.columns]

            # --- Flatten any multi-index or nested structure ---
            for col in df.columns:
                if isinstance(df[col], pd.DataFrame):
                    df[col] = df[col].iloc[:, 0]  # take first column if nested

            # --- Convert date safely ---
            if "Date" in df.columns:
                df["Date"] = pd.to_datetime(df["Date"], errors="coerce", dayfirst=True)

            # --- Convert numeric columns safely ---
            for num_col in ["Amount", "Quantity Ordered"]:
                if num_col in df.columns:
                    try:
                        if isinstance(df[num_col], pd.DataFrame):
                            df[num_col] = df[num_col].iloc[:, 0]
                        df[num_col] = pd.to_numeric(df[num_col], errors="coerce")
                    except Exception:
                        df[num_col] = pd.to_numeric(df[num_col].astype(str).str.extract(r'(\d+\.?\d*)')[0], errors="coerce")

            all_data.append(df)

    if all_data:
        return pd.concat(all_data, ignore_index=True)
    else:
        st.warning(f"No CSV files found in {folder}")
        return pd.DataFrame()

# --- Load Selected Data ---
df = load_data_from_folder(folder_path)
if df.empty:
    st.stop()

# --- Sidebar Filters ---
st.sidebar.header("🔍 Filters")

# Store filter
if "Store" in df.columns:
    store_options = sorted(df["Store"].dropna().unique())
    selected_stores = st.sidebar.multiselect("Select Store(s)", options=store_options, default=store_options)
    df = df[df["Store"].isin(selected_stores)]

# Date filter
if "Date" in df.columns:
    min_date, max_date = df["Date"].min(), df["Date"].max()
    if pd.notna(min_date) and pd.notna(max_date):
        date_range = st.sidebar.date_input("Select Date Range", [min_date, max_date])
        if len(date_range) == 2:
            start, end = date_range
            df = df[(df["Date"] >= pd.to_datetime(start)) & (df["Date"] <= pd.to_datetime(end))]

# --- 1️⃣ Summary Metrics ---
st.subheader("📈 Summary Metrics")

total_sales = df["Amount"].sum() if "Amount" in df.columns else 0
total_orders = len(df)
unique_stores = df["Store"].nunique() if "Store" in df.columns else 0

col1, col2, col3 = st.columns(3)
col1.metric("💰 Total Sales", f"₹{total_sales:,.0f}")
col2.metric("🧾 Total Orders", total_orders)
col3.metric("🏬 Stores", unique_stores)

st.divider()

# --- 2️⃣ Store-wise Sales ---
if "Store" in df.columns and "Amount" in df.columns:
    st.subheader("🏬 Store-wise Sales")
    store_summary = (
        df.groupby("Store")["Amount"]
        .sum()
        .sort_values(ascending=False)
    )
    st.bar_chart(store_summary, use_container_width=True)

st.divider()

# --- 3️⃣ Product Performance ---
if "Product" in df.columns:
    st.subheader("🧾 Product Performance")
    summary_cols = [c for c in ["Quantity Ordered", "Amount"] if c in df.columns]
    product_summary = (
        df.groupby("Product")[summary_cols]
        .sum()
        .sort_values(by=summary_cols[0], ascending=False)
    )
    st.dataframe(product_summary, use_container_width=True)

st.divider()

# --- 4️⃣ Detailed Orders Table ---
st.subheader(f"📋 Order Details ({selected_source})")
st.dataframe(df, use_container_width=True)

# --- 5️⃣ Download Filtered Data ---
st.markdown("### 💾 Download Filtered Data")

# CSV version
csv_data = df.to_csv(index=False).encode('utf-8')
st.download_button(
    label="⬇️ Download as CSV",
    data=csv_data,
    file_name=f"filtered_{selected_source.lower()}_data.csv",
    mime="text/csv",
)

# Excel version
excel_buffer = BytesIO()
with pd.ExcelWriter(excel_buffer, engine="xlsxwriter") as writer:
    df.to_excel(writer, index=False, sheet_name="Filtered Data")
excel_data =
