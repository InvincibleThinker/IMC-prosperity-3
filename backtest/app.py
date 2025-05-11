# app.py
import streamlit as st
import os
from backtester import Backtester


def main():
    st.set_page_config(layout="wide")
    st.title("Algorithmic Trading Backtest Dashboard")

    # 1. Directory handling with error checking
    data_dir = "historical_data"
    try:
        # Create directory if it doesn't exist
        os.makedirs(data_dir, exist_ok=True)

        # Get list of historical files
        files = [f for f in os.listdir(data_dir) if f.endswith('.csv')]

        if not files:
            st.warning(f"No CSV files found in {data_dir} directory")
            return

        # 2. File selection
        selected_file = st.selectbox("Select historical data", files)
        file_path = os.path.join(data_dir, selected_file)

        # 3. Backtest execution
        backtester = Backtester(file_path)
        results = backtester.run_backtest()

        # [Your visualization code here]

    except PermissionError:
        st.error(f"Permission denied to access directory: {data_dir}")
    except Exception as e:
        st.error(f"Error initializing directory: {str(e)}")


if __name__ == "__main__":
    main()
