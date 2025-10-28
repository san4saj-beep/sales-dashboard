import streamlit as st
import pandas as pd
import os

# Streamlit page setup
st.set_page_config(page_title="Sales Dashboard", layout="wide")

st.title("📊 Unified Sales Dashboard")

# Dropdown to select data source
data_source = st.selectbox("Select Data Source", ["POS", "Online", "B2B"])

# Define folder paths
base_path = "/mount/src/sales-dashboard"
folders = {
    "POS": os.path.join(base_path, "pos_data"),
    "Online": os.path.join(base_path, "online_data"),
    "B2B": os.path.join(base_path, "B2B"),
}

folder_path = folders[data_source]

# Helper function to load Excel/CSV files from a folder
def load_data_from_folder(folder):
    all_files = [
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if f.endswith((".xlsx", ".csv"))
    ]
    dfs = []
    for file in all_files:
        try:
            if file.endswith(".csv"):
                df = pd.read_csv(file)
            else:
                df = pd.read_excel(file)
            df["SourceFile"] = os.path.basename(file)
            dfs.append(df)
        except Exception as e:
            st.warning(f"⚠️ Could not read {file}: {e}")
    if dfs:
        return pd.concat(dfs, ignore_index=True)
    else:
        return pd.DataFrame()

# --- POS / Online Logic ---
if data_source in ["POS", "Online"]:
    df = load_data_from_folder(folder_path)

    if df.empty:
        st.warning(f"No data found in {folder_path}")
        st.stop()

    # Convert dates and numeric columns safely
    for col in df.columns:
        if "date" in col.lower():
            df[col] = pd.to_datetime(df[col], errors="coerce")

    if "Amount" in df.columns:
        df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
    if "Quantity Ordered" in df.columns:
        df["Quantity Ordered"] = pd.to_numeric(df["Quantity Ordered"], errors="coerce")

    # Summary metrics
    total_sales = df["Amount"].sum() if "Amount" in df.columns else 0
    total_qty = df["Quantity Ordered"].sum() if "Quantity Ordered" in df.columns else 0
    total_orders = df.shape[0]

    st.markdown("### 📈 Summary Metrics")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Sales", f"₹{total_sales:,.0f}")
    col2.metric("Total Quantity", f"{total_qty:,.0f}")
    col3.metric("Total Orders", f"{total_orders:,}")

    # Grouped sales by Store (if available)
    if "Store" in df.columns:
        store_summary = df.groupby("Store")["Amount"].sum().reset_index()
        st.bar_chart(store_summary.set_index("Store"))

    st.dataframe(df)

# --- B2B Logic (Custom Nested Format) ---
elif data_source == "B2B":
    df = load_data_from_folder(folder_path)

    if df.empty:
        st.warning(f"No data found in {folder_path}")
        st.stop()

    # Identify header rows (those with "Voucher No.")
    header_mask = df["Voucher No."].notna()
    headers = df[header_mask].reset_index()

    invoice_rows = []
    for i, row in headers.iterrows():
        invoice_no = row["Voucher No."]
        vendor = row["Particulars"]
        date = row["Date"]
        start_idx = row["index"]
        end_idx = headers["index"][i + 1] if i + 1 < len(headers) else len(df)

        items = df.iloc[start_idx + 1:end_idx]
        items = items[["Particulars", "Quantity", "Rate", "Value"]].dropna(how="all")

        invoice_rows.append({
            "Date": date,
            "Vendor": vendor,
            "Invoice No": invoice_no,
            "Item Count": len(items),
            "Invoice Total": row["Value"],
            "Items": items
        })

    b2b_summary = pd.DataFrame(invoice_rows)

    # --- Filters ---
    st.markdown("### 🧾 B2B Invoices Summary")
    date_filter = st.date_input("Filter by Date", [])
    search_invoice = st.text_input("🔍 Search Invoice No")

    filtered_df = b2b_summary.copy()
    if date_filter:
        filtered_df = filtered_df[filtered_df["Date"].isin(pd.to_datetime(date_filter))]
    if search_invoice:
        filtered_df = filtered_df[filtered_df["Invoice No"].astype(str).str.contains(search_invoice)]

    # --- Display Summary ---
    st.dataframe(filtered_df[["Date", "Vendor", "Invoice No", "Invoice Total", "Item Count"]])

    # --- View Items when invoice selected ---
    selected_invoice = st.selectbox("Select Invoice to view items", filtered_df["Invoice No"])
    selected_items = filtered_df.loc[filtered_df["Invoice No"] == selected_invoice, "Items"].values[0]

    st.markdown(f"### 📦 Items under Invoice **{selected_invoice}**")
    st.dataframe(selected_items)
