import streamlit as st
import pandas as pd
import glob
import os

st.set_page_config(page_title="Sales Dashboard", layout="wide")
st.title("📊 Daily Store Sales Dashboard")

# Folder where all sales CSVs are stored
folder_path = "sales_data"
files = glob.glob(os.path.join(folder_path, "*.csv"))

if not files:
    st.warning("No sales files found in the folder yet.")
else:
    # Read and merge all files
    df_list = []
    for f in files:
        try:
            data = pd.read_csv(f)
            df_list.append(data)
        except Exception as e:
            st.error(f"Error reading {f}: {e}")

    df = pd.concat(df_list, ignore_index=True)

    # Expected columns
    expected_cols = ['Date', 'Store', 'Product', 'Quantity Ordered', 'Size', 'Amount']
    missing = [col for col in expected_cols if col not in df.columns]

    if missing:
        st.error(f"Missing columns: {missing}")
    else:
        # Clean up and convert datatypes
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df['Quantity Ordered'] = pd.to_numeric(df[']()_
