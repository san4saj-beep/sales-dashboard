import streamlit as st
import pandas as pd
import numpy as np
import os
import glob
from io import BytesIO

# -------------------- Config --------------------
st.set_page_config(page_title="Unified Dashboard", layout="wide")
st.title("📊 Unified Sales + Inventory Dashboard")

BASE_PATH = "/mount/src/sales-dashboard"
FOLDERS = {
    "POS": os.path.join(BASE_PATH, "sales_data"),
    "Online": os.path.join(BASE_PATH, "online_data"),
    "B2B": os.path.join(BASE_PATH, "B2B"),
    "Inventory": os.path.join(BASE_PATH, "inventory"),
}
# fallback sample uploaded by user
SAMPLE_INVENTORY_FILE = "/mnt/data/sample_invnteoy.xlsx"

# -------------------- Helpers --------------------
def load_data_from_folder(folder):
    if not os.path.exists(folder):
        return pd.DataFrame()
    patterns = [os.path.join(folder, "*.xlsx"), os.path.join(folder, "*.xls"), os.path.join(folder, "*.csv")]
    files = []
    for p in patterns:
        files.extend(glob.glob(p))
    dfs = []
    for f in sorted(files):
        try:
            if f.lower().endswith((".xlsx", ".xls")):
                df = pd.read_excel(f, engine="openpyxl")
            else:
                df = pd.read_csv(f)
            df["SourceFile"] = os.path.basename(f)
            dfs.append(df)
        except Exception as e:
            st.warning(f"Could not read {f}: {e}")
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

def find_latest_file(folder):
    patterns = [os.path.join(folder, "*.xlsx"), os.path.join(folder, "*.xls"), os.path.join(folder, "*.csv")]
    files = []
    for p in patterns:
        files.extend(glob.glob(p))
    return max(files, key=os.path.getmtime) if files else None

def to_excel_bytes(df):
    out = BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Sheet1")
    return out.getvalue()

# -------------------- Sidebar Navigation (Option B) --------------------
st.sidebar.title("Dashboard")
section = st.sidebar.radio("Choose section", ["Sales", "Inventory"])

# Sales sub-selection
sales_source = None
if section == "Sales":
    st.sidebar.markdown("### Sales")
    sales_source = st.sidebar.selectbox("Select Sales Source", ["POS", "Online", "B2B"])
    data_source = sales_source
else:
    data_source = "Inventory"

# -------------------- SALES: POS / Online --------------------
if data_source in ["POS", "Online"]:
    folder_path = FOLDERS[data_source]
    df = load_data_from_folder(folder_path)

    if df.empty:
        st.warning(f"No data found in `{folder_path}`. Place .csv/.xlsx files there.")
        st.stop()

    # normalize
    df.columns = [str(c).strip() for c in df.columns]

    # detect and parse date
    date_cols = [c for c in df.columns if "date" in c.lower()]
    date_col = date_cols[0] if date_cols else None
    if date_col:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")

    # numeric conversions
    if "Amount" in df.columns:
        df["Amount"] = pd.to_numeric(df["Amount"].astype(str).str.replace(",", ""), errors="coerce")
    if "Quantity Ordered" in df.columns:
        df["Quantity Ordered"] = pd.to_numeric(df["Quantity Ordered"].astype(str).str.replace(",", ""), errors="coerce")

    # Filters in sidebar
    st.sidebar.header("Filters")
    store_filter = "All"
    if "Store" in df.columns:
        store_filter = st.sidebar.selectbox("Store", ["All"] + sorted(df["Store"].dropna().unique().tolist()))
    # date range filter (works for whole month)
    if date_col:
        date_min = df[date_col].min()
        date_max = df[date_col].max()
        date_range = st.sidebar.date_input("Date Range", value=[date_min.date() if pd.notna(date_min) else None,
                                                                 date_max.date() if pd.notna(date_max) else None])
    else:
        date_range = []

    # apply filters
    filtered_df = df.copy()
    if store_filter != "All" and "Store" in df.columns:
        filtered_df = filtered_df[filtered_df["Store"] == store_filter]
    if date_col and isinstance(date_range, (list, tuple)) and len(date_range) == 2 and date_range[0] and date_range[1]:
        start, end = date_range
        filtered_df = filtered_df[(filtered_df[date_col].dt.date >= start) & (filtered_df[date_col].dt.date <= end)]

    # KPIs
    total_sales = filtered_df["Amount"].sum() if "Amount" in filtered_df.columns else 0
    total_qty = filtered_df["Quantity Ordered"].sum() if "Quantity Ordered" in filtered_df.columns else 0

    st.subheader("📈 Overall Summary")
    c1, c2 = st.columns(2)
    c1.metric("Total Quantity Sold", f"{total_qty:,.0f}")
    c2.metric("Total Sales", f"₹{total_sales:,.0f}")

    # Store-wise summary
    if "Store" in filtered_df.columns:
        st.subheader("🏬 Store-wise Sales Summary")
        store_summary = filtered_df.groupby("Store").agg(Total_Sales=("Amount", "sum")).reset_index().sort_values("Total_Sales", ascending=False)
        st.dataframe(store_summary, use_container_width=True)

    # Product-level summary
    product_col = "Product" if "Product" in filtered_df.columns else None
    qty_col = "Quantity Ordered" if "Quantity Ordered" in filtered_df.columns else None
    if product_col and qty_col:
        product_summary = filtered_df.groupby(product_col).agg(Total_Qty=(qty_col, "sum"), Total_Amount=("Amount", "sum")).reset_index().sort_values("Total_Amount", ascending=False)
        st.subheader("🏷️ Product-wise Sales Summary")
        st.dataframe(product_summary, use_container_width=True)
    else:
        st.info("Product or Quantity columns not found for product summary.")

# -------------------- B2B SECTION --------------------
elif data_source == "B2B":
    folder_path = FOLDERS["B2B"]
    raw = load_data_from_folder(folder_path)

    if raw.empty:
        st.warning(f"No data found in `{folder_path}`.")
        st.stop()

    raw.columns = [str(c).strip() for c in raw.columns]

    if "Voucher No." not in raw.columns or "Particulars" not in raw.columns:
        st.error("B2B files must include 'Voucher No.' and 'Particulars' columns.")
        st.stop()

    # rename and forward-fill
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

    # detect item rows
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

    # Pre-tax numeric
    if value_col:
        items_df[value_col] = (items_df[value_col].astype(str)
                               .str.replace("Dr", "", regex=False)
                               .str.replace("Cr", "", regex=False)
                               .str.replace(",", "", regex=False))
        items_df["PreTaxNumeric"] = pd.to_numeric(items_df[value_col], errors="coerce")
    else:
        items_df["PreTaxNumeric"] = pd.NA

    # quantity numeric
    if "Quantity" in items_df.columns:
        items_df["QuantityNumeric"] = pd.to_numeric(items_df["Quantity"].astype(str).str.extract(r"(\d+)")[0], errors="coerce")
    else:
        items_df["QuantityNumeric"] = pd.NA

    # tax detection
    tax_cols = [c for c in items_df.columns if any(x.lower() in c.lower() for x in ["igst", "cgst", "sgst", "gst"])]
    for tc in tax_cols:
        items_df[tc] = (items_df[tc].astype(str)
                        .str.replace("Dr", "", regex=False)
                        .str.replace("Cr", "", regex=False)
                        .str.replace(",", "", regex=False))
        items_df[tc + "_Numeric"] = pd.to_numeric(items_df[tc], errors="coerce")

    # shipping detection
    shipping_candidates = [c for c in items_df.columns if any(x in c.lower() for x in ["shipping", "freight", "delivery"])]
    shipping_col = shipping_candidates[0] if shipping_candidates else None
    if shipping_col:
        items_df[shipping_col] = (items_df[shipping_col].astype(str)
                                  .str.replace("Dr", "", regex=False)
                                  .str.replace("Cr", "", regex=False)
                                  .str.replace(",", "", regex=False))
        items_df["ShippingNumeric"] = pd.to_numeric(items_df[shipping_col], errors="coerce")
    else:
        items_df["ShippingNumeric"] = 0.0

    # compute tax total and gross per item
    if tax_cols:
        tax_numeric_cols = [tc + "_Numeric" for tc in tax_cols]
        items_df["TaxTotalNumeric"] = items_df[tax_numeric_cols].sum(axis=1, min_count=1)
    else:
        items_df["TaxTotalNumeric"] = 0.0
    items_df["GrossSaleNumeric"] = items_df["PreTaxNumeric"].fillna(0) + items_df["TaxTotalNumeric"].fillna(0) + items_df["ShippingNumeric"].fillna(0)

    # build invoice summary
    voucher_list = raw["Voucher No."].dropna().unique().tolist()
    invoice_records = []
    for v in voucher_list:
        inv_rows = raw[raw["Voucher No."] == v]
        header_rows = inv_rows[inv_rows["Gross Total"].notna()] if "Gross Total" in inv_rows.columns else pd.DataFrame()
        if not header_rows.empty:
            header = header_rows.iloc[0]
        else:
            header = inv_rows.iloc[0]

        inv_date = pd.to_datetime(header.get("Date", pd.NaT), errors="coerce") if "Date" in header.index else pd.NaT
        vendor = header.get("Particulars", "")
        inv_items = items_df[items_df["Voucher No."] == v].copy()

        pre_tax_total = inv_items["PreTaxNumeric"].sum(min_count=1)
        gross_from_items = inv_items["GrossSaleNumeric"].sum(min_count=1)

        gross_sale = gross_from_items
        if "Gross Total" in header.index and pd.notna(header.get("Gross Total", None)) and str(header.get("Gross Total")).strip() != "":
            gt = str(header.get("Gross Total", "")).replace("Dr", "").replace("Cr", "").replace(",", "")
            try:
                header_gt = float(gt)
                gross_sale = header_gt
            except Exception:
                pass

        # header shipping addition if present and not included in items
        if shipping_col and shipping_col in header.index:
            try:
                sh = str(header.get(shipping_col, "")).replace("Dr", "").replace("Cr", "").replace(",", "")
                shv = float(sh) if sh != "" else 0.0
                if inv_items["ShippingNumeric"].sum(min_count=1) in (0, np.nan):
                    gross_sale = (gross_sale if gross_sale else gross_from_items) + shv
            except Exception:
                pass

        invoice_records.append({
            "Date": inv_date,
            "Vendor": vendor,
            "Voucher No.": v,
            "Item Count": len(inv_items),
            "Pre-Tax Total": pre_tax_total,
            "Gross Sale": gross_sale
        })

    invoices_df = pd.DataFrame(invoice_records)

    # B2B filters in sidebar
    st.sidebar.header("B2B Filters")
    vendor_options = ["All"] + sorted(invoices_df["Vendor"].dropna().unique().tolist()) if not invoices_df.empty else ["All"]
    vendor_filter = st.sidebar.selectbox("Vendor", vendor_options)
    if vendor_filter != "All":
        invoices_df = invoices_df[invoices_df["Vendor"] == vendor_filter]

    date_min = invoices_df["Date"].min() if not invoices_df.empty else pd.NaT
    date_max = invoices_df["Date"].max() if not invoices_df.empty else pd.NaT
    if pd.isna(date_min) or pd.isna(date_max):
        date_range = st.sidebar.date_input("Date Range", value=[])
    else:
        date_range = st.sidebar.date_input("Date Range", value=[date_min.date(), date_max.date()])
    if isinstance(date_range, (list, tuple)) and len(date_range) == 2 and date_range[0] and date_range[1]:
        start, end = date_range
        invoices_df = invoices_df[(invoices_df["Date"].dt.date >= start) & (invoices_df["Date"].dt.date <= end)]

    search_invoice = st.sidebar.text_input("Search Invoice No")
    if search_invoice:
        invoices_df = invoices_df[invoices_df["Voucher No."].astype(str).str.contains(search_invoice, case=False, na=False)]

    # KPIs
    total_invoices = len(invoices_df)
    total_vendors = invoices_df["Vendor"].nunique()
    total_pretax = invoices_df["Pre-Tax Total"].sum()
    total_gross = invoices_df["Gross Sale"].sum()

    st.subheader("🧾 B2B Summary")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Invoices", total_invoices)
    c2.metric("Unique Vendors", total_vendors)
    c3.metric("Total Pre-Tax Sales", f"₹{total_pretax:,.0f}")
    c4.metric("Total Gross Sales", f"₹{total_gross:,.0f}")

    st.dataframe(invoices_df.sort_values("Date", ascending=False).reset_index(drop=True), use_container_width=True)

    # drilldown
    if not invoices_df.empty:
        selected_invoice = st.selectbox("Select Invoice to View Items", invoices_df["Voucher No."].tolist())
        selected_items = items_df[items_df["Voucher No."] == selected_invoice].copy()
        if not selected_items.empty:
            display_cols = [c for c in ["Particulars", "Quantity", "Rate", value_col, "PreTaxNumeric", "TaxTotalNumeric", "ShippingNumeric", "GrossSaleNumeric"] if c in selected_items.columns]
            st.subheader(f"📦 Items under Invoice {selected_invoice}")
            st.dataframe(selected_items[display_cols].reset_index(drop=True), use_container_width=True)
            total_qty = selected_items["QuantityNumeric"].sum(min_count=1) if "QuantityNumeric" in selected_items.columns else np.nan
            total_pre_tax = selected_items["PreTaxNumeric"].sum(min_count=1)
            total_gross_items = selected_items["GrossSaleNumeric"].sum(min_count=1)
            st.markdown(f"**Computed from items:** Total Qty = {int(total_qty) if not pd.isna(total_qty) else 'N/A'} • Pre-Tax = ₹{total_pre_tax:,.2f} • Gross (items) = ₹{total_gross_items:,.2f}")
        else:
            st.info("No item lines found for selected invoice.")

# -------------------- INVENTORY SECTION --------------------
elif data_source == "Inventory":
    inv_folder = FOLDERS["Inventory"]
    latest = None
    if os.path.exists(inv_folder):
        latest = find_latest_file(inv_folder)
    if not latest:
        latest = SAMPLE_INVENTORY_FILE
        st.info(f"No inventory files in `{inv_folder}` — using sample file `{os.path.basename(SAMPLE_INVENTORY_FILE)}`.")
    else:
        st.info(f"Using inventory file: `{os.path.basename(latest)}`")

    try:
        inv_df = pd.read_excel(latest, engine="openpyxl") if str(latest).lower().endswith((".xlsx", ".xls")) else pd.read_csv(latest)
    except Exception as e:
        st.error(f"Failed to read inventory file `{latest}`: {e}")
        st.stop()

    inv_df.columns = [str(c).strip() for c in inv_df.columns]

    # mapping confirmed by you
    def find_col(cols, candidates):
        low = {c.lower(): c for c in cols}
        for cand in candidates:
            if cand.lower() in low:
                return low[cand.lower()]
        for cand in candidates:
            for k in low:
                if cand.lower() in k:
                    return low[k]
        return None

    product_col = find_col(inv_df.columns, ["Item Type Name", "Product Name", "Product", "Item Name", "Item"])
    date_col = find_col(inv_df.columns, ["Date", "Updated"])
    sku_col = find_col(inv_df.columns, ["Item SkuCode", "ItemSkuCode", "SKU", "Sku", "SkuCode"])
    inventory_col = find_col(inv_df.columns, ["Inventory", "Open Sale", "Open Sale Inventory", "Stock", "Qty", "Quantity"])
    cost_col = find_col(inv_df.columns, ["Cost Price", "Cost", "CostPrice", "Unit Cost"])
    facility_col = find_col(inv_df.columns, ["Facility", "Store", "Location"])
    category_col = find_col(inv_df.columns, ["Category Name", "Category", "CategoryName"])
    brand_col = find_col(inv_df.columns, ["Brand"])

    keep_cols = []
    mapping = {}
    if facility_col:
        keep_cols.append(facility_col); mapping[facility_col] = "Facility"
    if date_col:
        keep_cols.append(date_col); mapping[date_col] = "Date"
    if product_col:
        keep_cols.append(product_col); mapping[product_col] = "Product"
    if sku_col:
        keep_cols.append(sku_col); mapping[sku_col] = "SKU"
    if category_col:
        keep_cols.append(category_col); mapping[category_col] = "Category"
    if brand_col:
        keep_cols.append(brand_col); mapping[brand_col] = "Brand"
    if inventory_col:
        keep_cols.append(inventory_col); mapping[inventory_col] = "Inventory"
    if cost_col:
        keep_cols.append(cost_col); mapping[cost_col] = "Cost Price"

    if not keep_cols:
        st.error("Could not find expected inventory columns (Product, Date, SKU, Inventory, Cost Price).")
        st.stop()

    inv = inv_df[keep_cols].copy()
    inv.rename(columns=mapping, inplace=True)

    # ensure presence
    for c in ["Product", "SKU", "Facility", "Category", "Brand", "Inventory", "Cost Price", "Date"]:
        if c not in inv.columns:
            inv[c] = pd.NA

    # types and cleaning
    inv["Date"] = pd.to_datetime(inv["Date"], errors="coerce") if "Date" in inv.columns else pd.NaT
    inv["Inventory"] = inv["Inventory"].astype(str).str.replace(",", "")
    inv["Inventory"] = inv["Inventory"].str.extract(r"([-+]?\d*\.?\d+)", expand=False)
    inv["Inventory"] = pd.to_numeric(inv["Inventory"], errors="coerce").fillna(0)
    inv["Cost Price"] = inv["Cost Price"].astype(str).str.replace(",", "")
    inv["Cost Price"] = inv["Cost Price"].str.extract(r"([-+]?\d*\.?\d+)", expand=False)
    inv["Cost Price"] = pd.to_numeric(inv["Cost Price"], errors="coerce").fillna(0)
    inv["InventoryValue"] = inv["Inventory"] * inv["Cost Price"]

    # Inventory filters
    st.sidebar.header("Inventory Filters")
    facilities = ["All"] + sorted(inv["Facility"].dropna().astype(str).unique().tolist()) if inv["Facility"].notna().any() else ["All"]
    selected_facility = st.sidebar.selectbox("Facility", facilities)
    categories = ["All"] + sorted(inv["Category"].dropna().astype(str).unique().tolist()) if inv["Category"].notna().any() else ["All"]
    selected_category = st.sidebar.selectbox("Category", categories)
    brands = ["All"] + sorted(inv["Brand"].dropna().astype(str).unique().tolist()) if inv["Brand"].notna().any() else ["All"]
    selected_brand = st.sidebar.selectbox("Brand", brands)

    # date range
    date_min = inv["Date"].min()
    date_max = inv["Date"].max()
    if pd.isna(date_min) or pd.isna(date_max):
        date_range = st.sidebar.date_input("Date range (file has no valid dates)", value=[])
    else:
        date_range = st.sidebar.date_input("Date range", value=[date_min.date(), date_max.date()])

    search_text = st.sidebar.text_input("Search Product or SKU")

    # apply filters
    filtered = inv.copy()
    if selected_facility != "All":
        filtered = filtered[filtered["Facility"].astype(str) == selected_facility]
    if selected_category != "All":
        filtered = filtered[filtered["Category"].astype(str) == selected_category]
    if selected_brand != "All":
        filtered = filtered[filtered["Brand"].astype(str) == selected_brand]
    if isinstance(date_range, (list, tuple)) and len(date_range) == 2 and date_range[0] and date_range[1]:
        start, end = date_range
        filtered = filtered[(filtered["Date"].dt.date >= start) & (filtered["Date"].dt.date <= end)]
    if search_text:
        mask = filtered["Product"].astype(str).str.contains(search_text, case=False, na=False) | filtered["SKU"].astype(str).str.contains(search_text, case=False, na=False)
        filtered = filtered[mask]

    # KPIs
    st.subheader("📋 Inventory Summary")
    total_inventory = filtered["Inventory"].sum()
    total_value = filtered["InventoryValue"].sum()
    c1, c2 = st.columns(2)
    c1.metric("Total Inventory (Qty)", f"{total_inventory:,.0f}")
    c2.metric("Total Inventory Value (₹)", f"{total_value:,.2f}")

    # category summary
    if "Category" in filtered.columns and filtered["Category"].notna().any():
        cat_summary = filtered.groupby("Category").agg(Total_Qty=("Inventory", "sum"), Total_Value=("InventoryValue", "sum")).reset_index().sort_values("Total_Value", ascending=False)
        st.subheader("📊 Category-level Summary")
        st.dataframe(cat_summary, use_container_width=True)

    # product table
    st.subheader("🧾 Product-level Inventory")
    display_cols = [c for c in ["Facility", "Date", "Product", "SKU", "Category", "Brand", "Inventory", "Cost Price", "InventoryValue"] if c in filtered.columns]
    st.dataframe(filtered[display_cols].sort_values("InventoryValue", ascending=False).reset_index(drop=True), use_container_width=True)

    # download
    if not filtered.empty:
        excel_bytes = to_excel_bytes(filtered[display_cols])
        st.download_button("⬇️ Download filtered inventory (Excel)", data=excel_bytes, file_name="inventory_filtered.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.info("No rows to download for the current filter selection.")
