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

    df.columns = [str(c).strip() for c in df.columns]

    date_cols = [c for c in df.columns if "date" in c.lower()]
    if date_cols:
        df[date_cols[0]] = pd.to_datetime(df[date_cols[0]], errors="coerce")

    if "Amount" in df.columns:
        df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
    if "Quantity Ordered" in df.columns:
        df["Quantity Ordered"] = pd.to_numeric(df["Quantity Ordered"], errors="coerce")

    store_filter = "All"
    if "Store" in df.columns:
        store_filter = st.selectbox("Filter by Store", ["All"] + sorted(df["Store"].dropna().unique().tolist()))

    # ✅ Fixed date range filter
    date_col = date_cols[0] if date_cols else None
    date_min = df[date_col].min() if date_col else None
    date_max = df[date_col].max() if date_col else None
    date_range = st.date_input("Select Date Range", value=[date_min, date_max])

    filtered_df = df.copy()
    if store_filter != "All" and "Store" in df.columns:
        filtered_df = filtered_df[filtered_df["Store"] == store_filter]
    if date_col and date_range:
        if len(date_range) == 2:
            start, end = date_range
            filtered_df = filtered_df[
                (filtered_df[date_col].dt.date >= start) & (filtered_df[date_col].dt.date <= end)
            ]

    total_sales = filtered_df["Amount"].sum() if "Amount" in filtered_df.columns else 0
    total_qty = filtered_df["Quantity Ordered"].sum() if "Quantity Ordered" in filtered_df.columns else 0

    st.markdown("### 📈 Overall Summary")
    c1, c2 = st.columns(2)
    c1.metric("Total Quantity Sold", f"{total_qty:,.0f}")
    c2.metric("Total Sales", f"₹{total_sales:,.0f}")

    if "Store" in filtered_df.columns:
        st.markdown("### 🏬 Store-wise Sales Summary")
        store_summary = (
            filtered_df.groupby("Store")
            .agg({"Amount": "sum"})
            .reset_index()
            .rename(columns={"Amount": "Total Sales"})
        )
        st.dataframe(store_summary.sort_values(by="Total Sales", ascending=False), use_container_width=True)

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
# B2B SECTION
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

    if "Value" in raw.columns:
        raw.rename(columns={"Value": "Pre-Tax Value"}, inplace=True)

    raw["Voucher No."] = raw["Voucher No."].ffill()
    raw["Particulars"] = raw["Particulars"].ffill()

    if "Date" in raw.columns:
        raw["Date"] = pd.to_datetime(raw["Date"], errors="coerce", dayfirst=True)

    value_col = None
    for candidate in ["Pre-Tax Value", "Line Value", "Amount"]:
        if candidate in raw.columns:
            value_col = candidate
            break

    item_mask = pd.Series(False, index=raw.index)
    if value_col and value_col in raw.columns:
        item_mask = item_mask | raw[value_col].notna()
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
        items_df["PreTaxNumeric"] = pd.to_numeric(items_df[value_col], errors="coerce")
    else:
        items_df["PreTaxNumeric"] = pd.NA

    if "Quantity" in items_df.columns:
        items_df["QuantityNumeric"] = pd.to_numeric(
            items_df["Quantity"].astype(str).str.extract(r"(\d+)")[0],
            errors="coerce"
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

        inv_date = pd.to_datetime(header.get("Date", pd.NaT), errors="coerce")
        vendor = header.get("Particulars", "")
        inv_items = items_df[items_df["Voucher No."] == v].copy()

        pre_tax_total = inv_items["PreTaxNumeric"].sum(min_count=1)
        gross_sale = 0.0
        if "Gross Total" in header.index:
            gt = str(header.get("Gross Total", "")).replace("Dr", "").replace("Cr", "").replace(",", "")
            try:
                gross_sale = float(gt)
            except Exception:
                gross_sale = 0.0

        invoice_records.append({
            "Date": inv_date,
            "Vendor": vendor,
            "Voucher No.": v,
            "Item Count": len(inv_items),
            "Pre-Tax Total": pre_tax_total,
            "Gross Sale": gross_sale,
        })

    invoices_df = pd.DataFrame(invoice_records)

    # ✅ Vendor filter
    vendor_filter = st.selectbox("Filter by Vendor", ["All"] + sorted(invoices_df["Vendor"].dropna().unique().tolist()))
    if vendor_filter != "All":
        invoices_df = invoices_df[invoices_df["Vendor"] == vendor_filter]

    # ✅ Fixed date range filter
    date_min = invoices_df["Date"].min()
    date_max = invoices_df["Date"].max()
    date_range = st.date_input("Select Date Range", value=[date_min, date_max])
    if date_range and len(date_range) == 2:
        start, end = date_range
        invoices_df = invoices_df[
            (invoices_df["Date"].dt.date >= start) & (invoices_df["Date"].dt.date <= end)
        ]

    search_invoice = st.text_input("Search Invoice No")
    if search_invoice:
        invoices_df = invoices_df[
            invoices_df["Voucher No."].astype(str).str.contains(search_invoice, case=False, na=False)
        ]

    total_invoices = len(invoices_df)
    total_vendors = invoices_df["Vendor"].nunique()
    total_pretax = invoices_df["Pre-Tax Total"].sum()
    total_gross = invoices_df["Gross Sale"].sum()

    st.markdown("### 🧾 B2B Summary")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Invoices", total_invoices)
    c2.metric("Unique Vendors", total_vendors)
    c3.metric("Total Pre-Tax Sales", f"₹{total_pretax:,.0f}")
    c4.metric("Total Gross Sales", f"₹{total_gross:,.0f}")

    st.dataframe(invoices_df.sort_values("Date", ascending=False).reset_index(drop=True), use_container_width=True)

    if not invoices_df.empty:
        selected_invoice = st.selectbox("Select Invoice to View Items", invoices_df["Voucher No."].tolist())
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
            if "PreTaxNumeric" in selected_items.columns:
                display_cols.append("PreTaxNumeric")

            st.markdown(f"### 📦 Items under Invoice **{selected_invoice}**")
            st.dataframe(selected_items[display_cols].reset_index(drop=True), use_container_width=True)

            total_qty = selected_items["QuantityNumeric"].sum(min_count=1) if "QuantityNumeric" in selected_items.columns else np.nan
            total_pre_tax = selected_items["PreTaxNumeric"].sum(min_count=1)
            gross_sale_val = invoices_df.loc[invoices_df["Voucher No."] == selected_invoice, "Gross Sale"].values
            gross_display = f"₹{gross_sale_val[0]:,.2f}" if len(gross_sale_val) else "N/A"

            st.markdown(
                f"**Computed from items:** Total Qty = {int(total_qty) if not pd.isna(total_qty) else 'N/A'} "
                f"• Pre-Tax Value = ₹{total_pre_tax:,.2f} "
                f"• Gross Sale = {gross_display}"
            )
        else:
            st.info("No item lines found for selected invoice.")
