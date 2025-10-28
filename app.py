import streamlit as st
import pandas as pd
import os
import numpy as np

# --------------------------------------------------------------------
# Page setup
st.set_page_config(page_title="Sales Dashboard", layout="wide")
st.title("📊 Unified Sales Dashboard")

# --------------------------------------------------------------------
# Folder paths
data_folders = {
    "POS": "sales_data",
    "Online": "online_data",
    "B2B": "b2b_data"
}

# Sidebar - Source Selection
selected_source = st.sidebar.selectbox("Select Data Source", options=list(data_folders.keys()))
folder_path = data_folders[selected_source]

if not os.path.exists(folder_path):
    st.error(f"❌ Folder '{folder_path}' not found.")
    st.stop()

# --------------------------------------------------------------------
# Load Function
def load_data_from_folder(folder, source_type):
    all_data = []

    for file in os.listdir(folder):
        if not file.endswith((".xlsx", ".xls", ".csv")):
            continue
        file_path = os.path.join(folder, file)

        try:
            if file.endswith(".csv"):
                df = pd.read_csv(file_path)
            else:
                df = pd.read_excel(file_path)
        except Exception:
            continue

        df.columns = df.columns.str.strip()

        # POS
        if source_type == "POS":
            df["Date"] = pd.to_datetime(df.get("Date"), errors="coerce", dayfirst=True)
            df["Amount"] = pd.to_numeric(df.get("Amount"), errors="coerce")
            df["Store"] = df.get("Store", "POS")
            all_data.append(df[["Date", "Store", "Invoice No", "Amount"]])

        # Online
        elif source_type == "Online":
            df["Date"] = pd.to_datetime(df.get("Date"), errors="coerce", dayfirst=True)
            df["Amount"] = pd.to_numeric(df.get("Amount"), errors="coerce")
            df["Cha]()
