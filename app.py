import streamlit as st
import pandas as pd
import os

# Streamlit Setup
st.set_page_config(page_title="Sales Dashboard", layout="wide")
st.title("📊 Unified Sales Dashboard")

# Select data source
data_source = st.selectbox("Select Data Source", ["POS", "Online", "B2B"])

# Define folder paths
base_path = "/mount/src/sales-dashboard"
folders = {
    "POS": os.path.join(base_path, "pos_data"),
    "Online": os.path.join(base_path, "online_data"),
    "B2B": os.path.join(base_path, "B2B"),
}

folder_path = folders[data_source]

# Helper to load all files from a folder
def load_data_from_folder(folder):
    if not os.path.exists(folder):
        return pd.DataFrame()
    all_files = [
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if f.endswith((".xlsx", ".csv"))
    ]
    dfs = []
    for file in all_files:
        try:
            df = pd.read_excel(file) if file.endswith(".xlsx") else pd.read_csv(file)
            df["SourceFile"] = os.path.basename(file)
            dfs.append(df)
        except Exception as e:
            st.warning(f"⚠️ Could not read {file}: {e}")
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

# --------------------------------------------------
# POS / ONLINE SECTION
# --------------------------------------------------
if data_source in ["POS", "Online"]:
    df = load_data_from_folder(folder_path)

    if df.empty:
        st.warning(f"No data found in {folder_path}")
        st.stop()

    # Try to identify column names safely
    df.columns = [str(c).strip() for c in df.columns]

    # Parse dates and numeric columns
    date_cols = [c for c in df.columns if "date" in c.lower()]
    if date_cols:
        df[date_cols[0]] = pd.to_datetime(df[date_cols[0]], errors="coerce")

    if "Amount" in df.columns:
        df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
    if "Quantity Ordered" in df.columns:
        df["Quantity Ordered"] = pd.to_numeric(df["Quantity Ordered"], errors="coerce")

    # Filters
    store_filter = st.selectbox("Filter by Store", ["All"] + sorted(df["Store"].dropna().unique().tolist())) if "Store" in df.columns else "All"
    date_filter = st.date_input("Filter by Date", [])

    filtered_df = df.copy()
    if store_filter != "All" and "Store" in df.columns:
        filtered_df = filtered_df[filtered_df["Store"] == store_filter]
    if date_filter and date_cols:
        filtered_df = filtered_df[filtered_df[date_cols[0]].dt.date.isin(date_filter)]

    # Group by Product for summary
    product_col = "Product" if "Product" in filtered_df.columns else filtered_df.columns[0]
    qty_col = "Quantity Ordered" if "Quantity Ordered" in filtered_df.columns else None
    amount_col = "Amount" if "Amount" in filtered_df.columns else None

    grouped = filtered_df.groupby(product_col).agg({
        qty_col: "sum" if qty_col else "first",
        amount_col: "sum" if amount_col else "first"
    }).reset_index()

    total_qty = grouped[qty_col].sum() if qty_col else 0
    total_sales = grouped[amount_col].sum() if amount_col else 0

    st.markdown("### 📈 Summary")
    c1, c2 = st.columns(2)
    c1.metric("Total Quantity Sold", f"{total_qty:,.0f}")
    c2.metric("Total Sales", f"₹{total_sales:,.0f}")

    st.markdown("### 🏷️ Product-wise Sales Summary")
    st.dataframe(grouped)

    # Chart view
    if qty_col:
        st.bar_chart(grouped.set_index(product_col)[qty_col])

# --------------------------------------------------
# B2B SECTION
# --------------------------------------------------
elif data_source == "B2B":
    df = load_data_from_folder(folder_path)

    if df.empty:
        st.warning(f"No data found in {folder_path}")
        st.stop()

    df.columns = [str(c).strip() for c in df.columns]

    if "Voucher No." not in df.columns:
        st.warning("No 'Voucher No.' column found in B2B data.")
        st.stop()

    header_mask = df["Voucher No."].notna()
    headers = df[header_mask].reset_index()

    invoice_rows = []
    for i, row in headers.iterrows():
        invoice_no = row["Voucher No."]
        vendor = row["Particulars"]
        date = pd.to_datetime(row["Date"], errors="coerce")
        start_idx = row["index"]
        end_idx = headers["index"][i + 1] if i + 1 < len(headers) else len(df)

        items = df.iloc[start_idx + 1:end_idx]
        if all(col in items.columns for col in ["Particulars", "Quantity", "Rate", "Value"]):
            items = items[["Particulars", "Quantity", "Rate", "Value"]].dropna(how="all")

        invoice_rows.append({
            "Date": date,
            "Vendor": vendor,
            "Invoice No": invoice_no,
            "Item Count": len(items),
            "Invoice Total": pd.to_numeric(str(row.get("Value", 0)).replace(",", ""), errors="coerce"),
            "Items": items
        })

    b2b_summary = pd.DataFrame(invoice_rows)

    # Top summary metrics
    total_invoices = len(b2b_summary)
    total_vendors = b2b_summary["Vendor"].nunique()
    total_sales = b2b_summary["Invoice Total"].sum()

    st.markdown("### 🧾 B2B Summary")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Invoices", total_invoices)
    c2.metric("Unique Vendors", total_vendors)
    c3.metric("Total Sales", f"₹{total_sales:,.0f}")

    # Filters
    all_dates = sorted(b2b_summary["Date"].dropna().unique())
    date_filter = st.date_input("Filter by Date", [])
    search_invoice = st.text_input("Search Invoice No")

    filtered_df = b2b_summary.copy()
    if date_filter:
        filtered_df = filtered_df[filtered_df["Date"].dt.date.isin(date_filter)]
    if search_invoice:
        filtered_df = filtered_df[filtered_df["Invoice No"].astype(str).str.contains(search_invoice)]

    st.dataframe(filtered_df[["Date", "Vendor", "Invoice No", "Invoice Total", "Item Count"]])

    if not filtered_df.empty:
        selected_invoice = st.selectbox("Select Invoice to View Items", filtered_df["Invoice No"])
        selected_items = filtered_df.loc[filtered_df["Invoice No"] == selected_invoice, "Items"].values[0]
        st.markdown(f"### 📦 Items under Invoice **{selected_invoice}**")
        st.dataframe(selected_items)
