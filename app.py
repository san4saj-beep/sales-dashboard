import streamlit as st
import pandas as pd
import os

# --- Page Setup ---
st.set_page_config(page_title="Unified Sales Dashboard", layout="wide")
st.title("📊 Unified Sales Dashboard")

# --- Folder Paths ---
data_folders = {
    "POS": "sales_data",      # POS data
    "Online": "online_data",  # Online data
    "B2B": "B2B"              # ✅ Fixed folder path (uppercase)
}

# --- Dropdown to Choose Source ---
selected_source = st.sidebar.selectbox("Select Data Source", options=list(data_folders.keys()))
folder_path = data_folders[selected_source]


# ===================== POS & ONLINE DATA =====================
def load_pos_online_data(folder):
    all_data = []

    for file in os.listdir(folder):
        if file.endswith(".csv"):
            path = os.path.join(folder, file)
            df = pd.read_csv(path)

            # Clean duplicate columns
            df.columns = df.columns.astype(str).str.strip()
            df = df.loc[:, ~df.columns.duplicated()]
            df.columns = [c.strip().title() for c in df.columns]

            # Date conversion
            if "Date" in df.columns:
                df["Date"] = pd.to_datetime(df["Date"], errors="coerce", dayfirst=True)

            # Numeric conversion
            for col in ["Amount", "Quantity Ordered"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            all_data.append(df)

    return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()


# ===================== B2B DATA =====================
def load_b2b_data(folder):
    all_data = []

    for file in os.listdir(folder):
        if file.endswith(".xlsx"):
            path = os.path.join(folder, file)
            xls = pd.ExcelFile(path)

            for sheet in xls.sheet_names:
                raw_df = pd.read_excel(xls, sheet_name=sheet, header=None)
                parsed_rows = []
                current_invoice, current_date, current_store = None, None, None

                for _, row in raw_df.iterrows():
                    if pd.notna(row[1]) and "INV" in str(row[2]):
                        current_date = row[0]
                        current_store = str(row[1]).strip()
                        current_invoice = str(row[2]).strip()
                    elif pd.notna(row[0]) and "Total" not in str(row[0]):
                        parsed_rows.append({
                            "Date": current_date,
                            "Store": current_store,
                            "Invoice No": current_invoice,
                            "Product": str(row[0]).strip(),
                            "Quantity": str(row[1]).strip(),
                            "Rate": row[2] if len(row) > 2 else None,
                            "Value": row[3] if len(row) > 3 else None
                        })

                df = pd.DataFrame(parsed_rows)
                if not df.empty:
                    df["Date"] = pd.to_datetime(df["Date"], errors="coerce", dayfirst=True)
                    for col in ["Quantity", "Value"]:
                        df[col] = pd.to_numeric(df[col], errors="coerce")
                    all_data.append(df)

    return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()


# ===================== LOAD SELECTED DATA =====================
if selected_source in ["POS", "Online"]:
    df = load_pos_online_data(folder_path)
else:
    df = load_b2b_data(folder_path)

if df.empty:
    st.warning(f"No data found in {folder_path}")
    st.stop()


# ===================== FILTERS =====================
st.sidebar.header("🔍 Filters")

if "Date" in df.columns:
    min_date, max_date = df["Date"].min(), df["Date"].max()
    if pd.notna(min_date) and pd.notna(max_date):
        date_range = st.sidebar.date_input("Select Date Range", [min_date, max_date])
        if len(date_range) == 2:
            start, end = date_range
            df = df[(df["Date"] >= pd.to_datetime(start)) & (df["Date"] <= pd.to_datetime(end))]

if "Store" in df.columns:
    store_options = sorted(df["Store"].dropna().unique())
    selected_stores = st.sidebar.multiselect("Select Store(s)", options=store_options, default=store_options)
    df = df[df["Store"].isin(selected_stores)]


# ===================== DASHBOARD VIEW =====================
if selected_source in ["POS", "Online"]:
    # --- Summary Metrics ---
    st.subheader("📈 Summary Metrics")

    total_sales = df["Amount"].sum() if "Amount" in df.columns else 0
    total_orders = len(df)
    unique_stores = df["Store"].nunique() if "Store" in df.columns else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("💰 Total Sales", f"₹{total_sales:,.0f}")
    col2.metric("🧾 Total Orders", total_orders)
    col3.metric("🏬 Stores", unique_stores)

    st.divider()

    # --- Store-wise Sales ---
    if "Store" in df.columns and "Amount" in df.columns:
        st.subheader("🏬 Store-wise Sales")
        store_summary = df.groupby("Store")["Amount"].sum().sort_values(ascending=False)
        st.bar_chart(store_summary)

    st.divider()

    # --- Product Performance ---
    if "Product" in df.columns:
        st.subheader("🧾 Product Performance")
        summary_cols = [c for c in ["Quantity Ordered", "Amount"] if c in df.columns]
        product_summary = df.groupby("Product")[summary_cols].sum().sort_values(by=summary_cols[0], ascending=False)
        st.dataframe(product_summary)

else:
    # --- B2B Summary ---
    st.subheader("🏢 B2B Summary Metrics")

    total_sales = df["Value"].sum() if "Value" in df.columns else 0
    total_invoices = df["Invoice No"].nunique() if "Invoice No" in df.columns else 0
    total_stores = df["Store"].nunique() if "Store" in df.columns else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("💰 Total Sales", f"₹{total_sales:,.0f}")
    c2.metric("🧾 Total Invoices", total_invoices)
    c3.metric("🏬 Stores", total_stores)

    st.divider()

    # --- Invoice Summary ---
    st.subheader("📄 Invoice Summary")
    invoice_summary = (
        df.groupby(["Date", "Store", "Invoice No"])["Value"]
        .sum()
        .reset_index()
        .sort_values(by="Date", ascending=False)
    )

    selected_invoice = st.dataframe(
        invoice_summary,
        on_select="rerun",
        selection_mode="single-row",
        use_container_width=True
    )

    # --- Show Details for Selected Invoice ---
    if selected_invoice and "selection" in selected_invoice and selected_invoice["selection"]["rows"]:
        idx = selected_invoice["selection"]["rows"][0]
        inv_no = invoice_summary.iloc[idx]["Invoice No"]
        st.subheader(f"🧾 Items in Invoice: {inv_no}")
        items = df[df["Invoice No"] == inv_no][["Product", "Quantity", "Rate", "Value"]]
        st.dataframe(items, use_container_width=True)
