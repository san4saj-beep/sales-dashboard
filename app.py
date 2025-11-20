import streamlit as st
import pandas as pd
import numpy as np
import os
import glob
from io import BytesIO

# ---------- Page setup ----------
st.set_page_config(page_title="Unified Sales + Inventory Dashboard", layout="wide")
st.title("📊 Unified Sales + Inventory Dashboard")

# ---------- Top level toggle ----------
show_inventory = st.checkbox("Show Inventory Dashboard Instead of Sales", value=False)

# ---------- Base paths ----------
BASE_PATH = "/mount/src/sales-dashboard"
FOLDERS = {
    "POS": os.path.join(BASE_PATH, "sales_data"),
    "Online": os.path.join(BASE_PATH, "online_data"),
    "B2B": os.path.join(BASE_PATH, "B2B"),
}
# Inventory fallback: look for either 'inventory' or 'Inventory' folder
INV_FOLDER = os.path.join(BASE_PATH, "inventory")
if not os.path.exists(INV_FOLDER):
    alt = os.path.join(BASE_PATH, "Inventory")
    if os.path.exists(alt):
        INV_FOLDER = alt

# ---------- Helpers ----------
def load_files_from_folder(folder):
    """Load all .csv and .xlsx files (non-recursive) from `folder` into a single DataFrame."""
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

def to_excel_bytes(df):
    out = BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Sheet1")
    return out.getvalue()

# ---------- SALES DASHBOARD ----------
if not show_inventory:
    st.header("🛒 Sales Dashboard")

    data_source = st.selectbox("Select Data Source", ["POS", "Online", "B2B"])

    if data_source != "B2B":
        # POS / Online simple flow
        folder = FOLDERS.get(data_source)
        df = load_files_from_folder(folder)

        if df.empty:
            st.warning(f"No data found in {folder}")
        else:
            # normalize column names
            df.columns = [str(c).strip() for c in df.columns]

            # detect date column and convert
            date_cols = [c for c in df.columns if "date" in c.lower()]
            date_col = date_cols[0] if date_cols else None
            if date_col:
                df[date_col] = pd.to_datetime(df[date_col], errors="coerce")

            # numeric conversions
            if "Amount" in df.columns:
                df["Amount"] = pd.to_numeric(df["Amount"].astype(str).str.replace(",", ""), errors="coerce")
            if "Quantity Ordered" in df.columns:
                df["Quantity Ordered"] = pd.to_numeric(df["Quantity Ordered"].astype(str).str.replace(",", ""), errors="coerce")

            # Store filter
            if "Store" in df.columns:
                store_filter = st.selectbox("Filter by Store", ["All"] + sorted(df["Store"].dropna().unique().tolist()))
                if store_filter != "All":
                    df = df[df["Store"] == store_filter]

            # Date range filter
            if date_col:
                date_min = df[date_col].min()
                date_max = df[date_col].max()
                date_range = st.date_input("Select Date Range", value=[date_min, date_max])
                if isinstance(date_range, (list, tuple)) and len(date_range) == 2 and date_range[0] and date_range[1]:
                    s, e = date_range
                    df = df[(df[date_col].dt.date >= s) & (df[date_col].dt.date <= e)]

            # KPIs
            total_sales = df["Amount"].sum() if "Amount" in df.columns else 0
            total_qty = df["Quantity Ordered"].sum() if "Quantity Ordered" in df.columns else 0

            st.subheader("📈 Overall Summary")
            c1, c2 = st.columns(2)
            c1.metric("Total Quantity Sold", f"{total_qty:,.0f}")
            c2.metric("Total Sales", f"₹{total_sales:,.0f}")

            # Store-wise summary
            if "Store" in df.columns:
                st.subheader("🏬 Store-wise Sales Summary")
                store_summary = df.groupby("Store").agg(Total_Sales=("Amount", "sum")).reset_index().sort_values("Total_Sales", ascending=False)
                st.dataframe(store_summary, use_container_width=True)

            # Product-level summary
            product_col = "Product" if "Product" in df.columns else None
            qty_col = "Quantity Ordered" if "Quantity Ordered" in df.columns else None
            if product_col and qty_col:
                product_summary = df.groupby(product_col).agg(Total_Qty=(qty_col, "sum"), Total_Amount=("Amount", "sum")).reset_index().sort_values("Total_Amount", ascending=False)
                st.subheader("🏷️ Product-wise Sales Summary")
                st.dataframe(product_summary, use_container_width=True)
            else:
                st.info("Product or Quantity columns not found for product summary.")

    else:
        # --------- FULL B2B PARSING FLOW ----------
        folder = FOLDERS.get("B2B")
        raw = load_files_from_folder(folder)

        if raw.empty:
            st.warning(f"No data found in {folder}")
        else:
            raw.columns = [str(c).strip() for c in raw.columns]

            if "Voucher No." not in raw.columns or "Particulars" not in raw.columns:
                st.error("B2B files must include 'Voucher No.' and 'Particulars' columns.")
            else:
                # rename if needed
                if "Value" in raw.columns:
                    raw.rename(columns={"Value": "Pre-Tax Value"}, inplace=True)

                # forward fill voucher and particulars
                raw["Voucher No."] = raw["Voucher No."].ffill()
                raw["Particulars"] = raw["Particulars"].ffill()

                if "Date" in raw.columns:
                    raw["Date"] = pd.to_datetime(raw["Date"], errors="coerce", dayfirst=True)

                # detect value column / item rows
                value_col = None
                for candidate in ["Pre-Tax Value", "Line Value", "Amount", "Value"]:
                    if candidate in raw.columns:
                        value_col = candidate
                        break

                # item detection
                item_mask = pd.Series(False, index=raw.index)
                if value_col and value_col in raw.columns:
                    item_mask = item_mask | raw[value_col].notna()
                if "Quantity" in raw.columns:
                    item_mask = item_mask | raw["Quantity"].notna()
                # remove header rows if Gross Total present
                if "Gross Total" in raw.columns:
                    header_mask = raw["Gross Total"].notna()
                    item_mask = item_mask & (~header_mask)

                items_df = raw[item_mask].copy()

                for col in ["Voucher No.", "Particulars", "Quantity", "Rate", value_col]:
                    if col not in items_df.columns:
                        items_df[col] = np.nan

                # numeric conversions for pre-tax
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
                    items_df["QuantityNumeric"] = pd.to_numeric(items_df["Quantity"].astype(str).str.extract(r"([-+]?\d*\.?\d+)")[0], errors="coerce")
                else:
                    items_df["QuantityNumeric"] = pd.NA

                # detect tax columns (cgst/sgst/igst/gst)
                tax_cols = [c for c in items_df.columns if any(x in c.lower() for x in ["igst", "cgst", "sgst", "gst"])]
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
                    tax_numeric_cols = [tc + "_Numeric" for tc in tax_cols if tc + "_Numeric" in items_df.columns]
                    if tax_numeric_cols:
                        items_df["TaxTotalNumeric"] = items_df[tax_numeric_cols].sum(axis=1, min_count=1)
                    else:
                        items_df["TaxTotalNumeric"] = 0.0
                else:
                    items_df["TaxTotalNumeric"] = 0.0

                items_df["GrossSaleNumeric"] = items_df["PreTaxNumeric"].fillna(0) + items_df["TaxTotalNumeric"].fillna(0) + items_df["ShippingNumeric"].fillna(0)

                # Build invoice summary
                voucher_list = raw["Voucher No."].dropna().unique().tolist()
                invoice_records = []
                for v in voucher_list:
                    inv_rows = raw[raw["Voucher No."] == v]
                    header_rows = inv_rows[inv_rows["Gross Total"].notna()] if "Gross Total" in inv_rows.columns else pd.DataFrame()
                    header = header_rows.iloc[0] if not header_rows.empty else inv_rows.iloc[0]
                    inv_date = pd.to_datetime(header.get("Date", pd.NaT), errors="coerce") if "Date" in header.index else pd.NaT
                    vendor = header.get("Particulars", "")
                    inv_items = items_df[items_df["Voucher No."] == v].copy()

                    pre_tax_total = inv_items["PreTaxNumeric"].sum(min_count=1) if "PreTaxNumeric" in inv_items.columns else 0.0
                    gross_from_items = inv_items["GrossSaleNumeric"].sum(min_count=1) if "GrossSaleNumeric" in inv_items.columns else 0.0

                    gross_sale = gross_from_items
                    # prefer header Gross Total if present
                    if "Gross Total" in header.index and pd.notna(header.get("Gross Total", None)) and str(header.get("Gross Total")).strip() != "":
                        gt = str(header.get("Gross Total", "")).replace("Dr", "").replace("Cr", "").replace(",", "")
                        try:
                            header_gt = float(gt)
                            gross_sale = header_gt
                        except Exception:
                            pass

                    # header-level shipping addition if present and not included in items
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

                # B2B filters and UI
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
                total_vendors = invoices_df["Vendor"].nunique() if "Vendor" in invoices_df.columns else 0
                total_pretax = invoices_df["Pre-Tax Total"].sum() if "Pre-Tax Total" in invoices_df.columns else 0
                total_gross = invoices_df["Gross Sale"].sum() if "Gross Sale" in invoices_df.columns else 0

                st.subheader("🧾 B2B Summary")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Total Invoices", total_invoices)
                c2.metric("Unique Vendors", total_vendors)
                c3.metric("Total Pre-Tax Sales", f"₹{total_pretax:,.0f}")
                c4.metric("Total Gross Sales", f"₹{total_gross:,.0f}")

                st.dataframe(invoices_df.sort_values("Date", ascending=False).reset_index(drop=True), use_container_width=True)

                # drilldown items (if user wants)
                if not invoices_df.empty:
                    selected_invoice = st.selectbox("Select Invoice to View Items", invoices_df["Voucher No."].tolist())
                    selected_items = items_df[items_df["Voucher No."] == selected_invoice].copy()
                    if not selected_items.empty:
                        display_cols = [c for c in ["Particulars", "Quantity", "Rate", value_col, "PreTaxNumeric", "TaxTotalNumeric", "ShippingNumeric", "GrossSaleNumeric"] if c in selected_items.columns]
                        st.subheader(f"📦 Items under Invoice {selected_invoice}")
                        st.dataframe(selected_items[display_cols].reset_index(drop=True), use_container_width=True)
                        total_qty = selected_items["QuantityNumeric"].sum(min_count=1) if "QuantityNumeric" in selected_items.columns else np.nan
                        total_pre_tax = selected_items["PreTaxNumeric"].sum(min_count=1) if "PreTaxNumeric" in selected_items.columns else 0.0
                        total_gross_items = selected_items["GrossSaleNumeric"].sum(min_count=1) if "GrossSaleNumeric" in selected_items.columns else 0.0
                        st.markdown(f"**Computed from items:** Total Qty = {int(total_qty) if not pd.isna(total_qty) else 'N/A'} • Pre-Tax = ₹{total_pre_tax:,.2f} • Gross (items) = ₹{total_gross_items:,.2f}")
                    else:
                        st.info("No item lines found for selected invoice.")

# ---------- INVENTORY DASHBOARD ----------
else:
    st.header("📦 Inventory Dashboard")

    inv = load_files_from_folder(INV_FOLDER)

    if inv.empty:
        st.warning(f"No inventory files found in `{INV_FOLDER}`.")
    else:
        # normalize columns
        inv.columns = [str(c).strip() for c in inv.columns]

        # date detection
        date_cols = [c for c in inv.columns if "date" in c.lower()]
        date_col = date_cols[0] if date_cols else None
        if date_col:
            inv[date_col] = pd.to_datetime(inv[date_col], errors="coerce")

        # category detection
        category_col = None
        for c in ["Category", "category", "Item Category", "Group"]:
            if c in inv.columns:
                category_col = c
                break

        # category filter UI
        if category_col:
            cats = ["All"] + sorted(inv[category_col].dropna().unique().tolist())
            cat_sel = st.selectbox("Filter by Category", cats)
            if cat_sel != "All":
                inv = inv[inv[category_col] == cat_sel]

        # date filter UI: default to latest date
        if date_col:
            dmin = inv[date_col].min()
            dmax = inv[date_col].max()
            # default single-day snapshot: latest date
            default_start = dmax
            default_end = dmax
            date_range = st.date_input("Select Inventory Date (snapshot or range)", value=[default_start, default_end], min_value=dmin, max_value=dmax)
            if isinstance(date_range, (list, tuple)) and len(date_range) == 2 and date_range[0] and date_range[1]:
                s, e = date_range
                inv = inv[(inv[date_col].dt.date >= s) & (inv[date_col].dt.date <= e)]

        # show table
        st.subheader("📄 Inventory Records")
        st.dataframe(inv, use_container_width=True)

        # detect quantity/stock column
        qty_col = None
        for q in ["Qty", "Quantity", "Stock", "Closing Stock", "Open Sale", "Inventory"]:
            if q in inv.columns:
                qty_col = q
                break

        # total stock KPI
        if qty_col:
            # clean numeric
            inv[qty_col] = pd.to_numeric(inv[qty_col].astype(str).str.replace(",", ""), errors="coerce").fillna(0)
            total_stock = inv[qty_col].sum()
            st.metric("Total Stock", f"{total_stock:,.0f}")

        # category level summary
        if category_col and qty_col:
            st.subheader("📂 Category Level Inventory Summary")
            cat_summary = inv.groupby(category_col)[qty_col].sum().reset_index().rename(columns={qty_col: "Total Stock"}).sort_values("Total Stock", ascending=False)
            st.dataframe(cat_summary, use_container_width=True)

        # download filtered inventory
        if not inv.empty:
            try:
                excel_bytes = to_excel_bytes(inv)
                st.download_button("⬇️ Download filtered inventory (Excel)", data=excel_bytes, file_name="inventory_filtered.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            except Exception:
                csv_bytes = inv.to_csv(index=False).encode("utf-8")
                st.download_button("⬇️ Download filtered inventory (CSV)", data=csv_bytes, file_name="inventory_filtered.csv", mime="text/csv")
