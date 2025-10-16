import streamlit as st
import pandas as pd
import glob
import os

st.title("📊 Daily Sales Dashboard")

# Read all CSV files in the folder
folder_path = "sales_data"
files = glob.glob(os.path.join(folder_path, "*.csv"))

if not files:
    st.warning("No sales files found in the folder yet.")
else:
    df_list = []
    for f in files:
        df = pd.read_csv(f)
        df_list.append(df)
    data = pd.concat(df_list, ignore_index=True)

    # Expect columns: Date, Store, Amount
    if {'Date', 'Store', 'Amount'}.issubset(data.columns):
        data['Date'] = pd.to_datetime(data['Date'])

        st.subheader("📅 Daily Sales")
        daily_sales = data.groupby('Date')['Amount'].sum().reset_index()
        st.line_chart(daily_sales, x='Date', y='Amount')

        st.subheader("🏬 Store-wise Sales")
        store_sales = data.groupby('Store')['Amount'].sum().reset_index()
        st.bar_chart(store_sales, x='Store', y='Amount')

        total_sales = data['Amount'].sum()
        st.metric("💰 Total Sales", f"₹{total_sales:,.0f}")

    else:
        st.error("Your file must have 'Date', 'Store', and 'Amount' columns.")
