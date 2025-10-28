import streamlit as st
import pandas as pd
import os
import numpy as np

# Streamlit Setup
st.set_page_config(page_title="Sales Dashboard", layout="wide")
st.title("📊 Unified Sales Dashboard")

# Select data source
data_source = st.selectbox("Select Data Source", ["POS", "Online", "B2B"])

# Define folder paths
base_path = "/mount/src/sales-dashboard"
folders = {
    "POS": os.path.join(base_path, "sales_data"),
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

    # Normalize columns
    df.columns = [str(c).strip() for c in df.columns]

    # Date parsing
    date_cols = [c for c in df.columns if "date" in c.lower()]
    if date_cols:
        df[date_cols[0]] = pd.to_datetime(df[date_cols[0]], errors="coerce")

    # Numeric parsing
    if "Amount" in df.columns:
        df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
    if "Quantity Ordered" in df.columns:
        df["Quantity Ordered"] = pd.to_numeric(df["Quantity Ordered"], errors="coerce")

    # Filters
    store_filter = "All"
    if "Store" in df.columns:
        store_filter = st.selectbox("Filter by Store", ["All"] + sorted(df["Store"].dropna().unique().tolist()))
    date_filter = st.date_input("Filter by Date", [])

    filtered_df = df.copy()
    if store_filter != "All" and "Store" in df.columns:
        filtered_df = filtered_df[filtered_df["Store"] == store_filter]
    if date_filter and date_cols:
        if isinstance(date_filter, (list, tuple)) and len(date_filter) > 0:
            selected_dates = [d for d in date_filter]
            filtered_df = filtered_df[filtered_df[date_cols[0]].dt.date.isin(selected_dates)]
        else:
            filtered_df = filtered_df[filtered_df[date_cols[0]].dt.date == date_filter]

    # Compute Totals
    total_sales = filtered_df["Amount"].sum() if "Amount" in filtered_df.columns else 0
    total_qty = filtered_df["Quantity Ordered"].sum() if "Quantity Ordered" in filtered_df.columns else 0

    st.markdown("### 📈 Overall Summary")
    c1, c2 = st.columns(2)
    c1.metric("Total Quantity Sold", f"{total_qty:,.0f}")
    c2.metric("Total Sales", f"₹{total_sales:,.0f}")

    # --- Store-wise Summary (New Section) ---
    if "Store" in filtered_df.columns:
        st.markdown("### 🏬 Store-wise Sales Summary")
        store_summary = (
            filtered_df.groupby("Store")
            .agg({"Amount": "sum"})
            .reset_index()
            .rename(columns={"Amount": "Total Sales"})
        )
        st.dataframe(store_summary.sort_values(by="Total Sales", ascending=False), use_container_width=True)

    # --- Product-wise Summary ---
    product_col = "Product" if "Product" in filtered_df.columns else None
    qty_col = "Quantity Ordered" if "Quantity Ordered" in filtered_df.columns else None
    amount_col = "Amount" if "Amount" in filtered_df.columns else None

    if product_col and qty_col:
        grouped = (
            filtered_df.groupby(product_col)
            .agg({qty_col: "sum", amount_col: "sum"})
            .reset_index()
            .rename(columns={qty_col: "Total Qty", amount_col: "Total Amount"})
        )

        st.markdown("### 🏷️ Product-wise Sales Summary")
        st.dataframe(grouped.sort_values(by="Total Amount", ascending=False), use_container_width=True)
    else:
        st.info("Product or quantity columns not found in this dataset.")

# --------------------------------------------------
# B2B SECTION (UNCHANGED)
# --------------------------------------------------
elif data_source == "B2B":
    raw = load_data_from_folder(folder_path)

    if raw.empty:
        st.warning(f"No data found in {folder_path}")
        st.stop()

    raw.columns = [str(c).strip() for c in raw.columns]

    if "Voucher No." not in raw.columns or "Particulars" not in raw.columns:
        st.error("B2B files must include 'Voucher No.' and 'Particulars' columns.")
        st.stop()

    raw["Voucher No."] = raw["Voucher No."].ffill()
    raw["Particulars"] = raw["Particulars"].ffill()
    if "Date" in raw.columns:
        raw["Date"] = pd.to_datetime(raw["Date"], errors="coerce", dayfirst=True)

    value_col = None
    for candidate in ["Value", "Line Value", "Amount", "Gross Total"]:
        if candidate in raw.columns:
            value_col = candidate
            break

    item_mask = pd.Series(False, index=raw.index)
    if "Value" in raw.columns:
        item_mask = item_mask | raw["Value"].notna()
    if "Quantity" in raw.columns:
        item_mask = item_mask | raw["Quantity"].notna()
    if "Gross Total" in raw.columns:
        header_mask = raw["Gross Total"].notna()
        item_mask = item_mask & (~header_mask)

    items_df = raw[item_mask].copy()
    for col in ["Voucher No.", "Particulars", "Quantity", "Rate", value_col]:
        if col not in items_df.columns:
            items_df[col] = np.nan

    if value_col:
        items_df[value_col] = (
            items_df[value_col]
            .astype(str)
            .str.replace("Dr", "", regex=False)
            .str.replace("Cr", "", regex=False)
            .str.replace(",", "", regex=False)
        )
        items_df["LineValueNumeric"] = pd.to_numeric(items_df[value_col], errors="coerce")
    else:
        items_df["LineValueNumeric"] = pd.NA

    if "Quantity" in items_df.columns:
        items_df["QuantityNumeric"] = pd.to_numeric(
            items_df["Quantity"].astype(str).str.extract(r"(\d+)")[0],
            errors="coerce",
        )
    else:
        items_df["QuantityNumeric"] = pd.NA

    voucher_list = raw["Voucher No."].dropna().unique().tolist()
    invoice_records = []
    for v in voucher_list:
        inv_rows = raw[raw["Voucher No."] == v]
        header_rows = inv_rows[inv_rows["Gross Total"].notna()] if "Gross Total" in inv_rows.columns else pd.DataFrame()
        if not header_rows.empty:
            header = header_rows.iloc[0]
        else:
            header = inv_rows.iloc[0]

        inv_date = pd.to_datetime(header["Date"], errors="coerce") if "Date" in header.index else pd.NaT
        vendor = header.get("Particulars", "")
        inv_items = items_df[items_df["Voucher No."] == v].copy()

        total_value = inv_items["LineValueNumeric"].sum(min_count=1)
        if pd.isna(total_value) or total_value == 0:
            if "Gross Total" in header.index:
                gt = str(header.get("Gross Total", "")).replace("Dr", "").replace("Cr", "").replace(",", "")
                try:
                    total_value = float(gt)
                except Exception:
                    total_value = 0.0
            else:
                total_value = 0.0

        item_count = int(len(inv_items))
        invoice_records.append({
            "Date": inv_date,
            "Vendor": vendor,
            "Voucher No.": v,
            "Item Count": item_count,
            "Invoice Total": total_value
        })

    invoices_df = pd.DataFrame(invoice_records)

    total_invoices = len(invoices_df)
    total_vendors = invoices_df["Vendor"].nunique()
    total_sales = invoices_df["Invoice Total"].sum()

    st.markdown("### 🧾 B2B Summary")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Invoices", total_invoices)
    c2.metric("Unique Vendors", total_vendors)
    c3.metric("Total Sales", f"₹{total_sales:,.0f}")

    date_filter = st.date_input("Filter by Date (optional)", [])
    search_invoice = st.text_input("Search Invoice No")

    filtered_invoices = invoices_df.copy()
    if date_filter:
        if isinstance(date_filter, (list, tuple)):
            selected_dates = [pd.to_datetime(d).date() for d in date_filter]
            filtered_invoices = filtered_invoices[filtered_invoices["Date"].dt.date.isin(selected_dates)]
        else:
            filtered_invoices = filtered_invoices[filtered_invoices["Date"].dt.date == pd.to_datetime(date_filter).date()]

    if search_invoice:
        filtered_invoices = filtered_invoices[filtered_invoices["Voucher No."].astype(str).str.contains(search_invoice, case=False, na=False)]

    st.dataframe(filtered_invoices.sort_values("Date", ascending=False).reset_index(drop=True), use_container_width=True)

    if not filtered_invoices.empty:
        selected_invoice = st.selectbox("Select Invoice to View Items", filtered_invoices["Voucher No."].tolist())
        selected_items = items_df[items_df["Voucher No."] == selected_invoice].copy()
        if not selected_items.empty:
            display_cols = []
            if "Particulars" in selected_items.columns:
                display_cols.append("Particulars")
            if "Quantity" in selected_items.columns:
                display_cols.append("Quantity")
            if "Rate" in selected_items.columns:
                display_cols.append("Rate")
            if value_col in selected_items.columns:
                display_cols.append(value_col)
            if "LineValueNumeric" in selected_items.columns:
                selected_items["LineValueNumeric"] = selected_items["LineValueNumeric"].fillna(0)
                if "LineValueNumeric" not in display_cols:
                    display_cols.append("LineValueNumeric")

            st.markdown(f"### 📦 Items under Invoice **{selected_invoice}**")
            st.dataframe(selected_items[display_cols].reset_index(drop=True), use_container_width=True)

            total_qty = selected_items["QuantityNumeric"].sum(min_count=1) if "QuantityNumeric" in selected_items.columns else np.nan
            total_val = selected_items["LineValueNumeric"].sum(min_count=1)
            st.markdown(f"**Computed from items:** Total Qty = {int(total_qty) if not pd.isna(total_qty) else 'N/A'} • Total Value = ₹{total_val:,.2f}")
        else:
            st.info("No item lines found for selected invoice.")
