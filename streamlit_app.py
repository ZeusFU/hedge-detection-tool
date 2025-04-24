import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

st.set_page_config(page_title="Hedge Detection", layout="wide")
st.title("🔍 Hedge Trade Detection & Analysis")

# Upload file
uploaded_file = st.file_uploader("Upload CSV Trade Dataset", type=["csv"])

if uploaded_file is not None:
    try:
        df = pd.read_csv(uploaded_file, low_memory=False)

        # Normalize column names
        df.columns = df.columns.str.strip().str.lower()

        # Parse datetime columns
        df['open_datetime'] = pd.to_datetime(df['open_datetime'], errors='coerce')
        df['close_datetime'] = pd.to_datetime(df['close_datetime'], errors='coerce')

        # Drop rows with invalid datetime parsing
        df = df.dropna(subset=['open_datetime', 'close_datetime'])

        # Normalize asset types (e.g. MNQH5 → NQH5)
        def normalize_asset(asset):
            if isinstance(asset, str) and asset.startswith("MNQ"):
                return "NQ" + asset[3:]
            return asset

        df['normalized_asset'] = df['asset'].apply(normalize_asset)

        # Prepare candidate trades to compare
        hedges = []
        grouped = df.groupby('normalized_asset')

        for asset, group in grouped:
            group = group.sort_values('open_datetime')
            for i, trade in group.iterrows():
                for j, candidate in group.iterrows():
                    if trade['account_id'] == candidate['account_id']:
                        continue  # same account
                    if abs(trade['avg_market_entry'] - candidate['avg_market_entry']) > 5:
                        continue  # entry price difference too large
                    if trade['short_long'] == candidate['short_long']:
                        continue  # same direction, not a hedge
                    if candidate['open_datetime'] > trade['close_datetime']:
                        continue  # no overlap
                    if candidate['close_datetime'] < trade['open_datetime']:
                        continue  # no overlap
                    hedges.append({
                        'account_1': trade['account_id'],
                        'account_2': candidate['account_id'],
                        'user_1': trade['user_id'],
                        'user_2': candidate['user_id'],
                        'asset': asset,
                        'entry_1': trade['avg_market_entry'],
                        'entry_2': candidate['avg_market_entry'],
                        'open_1': trade['open_datetime'],
                        'open_2': candidate['open_datetime'],
                        'close_1': trade['close_datetime'],
                        'close_2': candidate['close_datetime'],
                        'direction_1': trade['short_long'],
                        'direction_2': candidate['short_long'],
                        'profit_1': trade['market_profit'],
                        'profit_2': candidate['market_profit'],
                    })

        hedge_df = pd.DataFrame(hedges)

        st.subheader("🔗 Potential Hedge Trades")
        st.write(f"Total Hedge Pairs Detected: {len(hedge_df)}")
        st.dataframe(hedge_df)

        st.subheader("📊 Summary Statistics")
        if not hedge_df.empty:
            user_hedge_stats = hedge_df.groupby(['user_1', 'user_2']).size().reset_index(name='hedge_count')
            account_hedge_stats = hedge_df.groupby(['account_1', 'account_2']).size().reset_index(name='hedge_count')

            st.write("**Users Involved in Hedging**")
            st.dataframe(user_hedge_stats)

            st.write("**Accounts Involved in Hedging**")
            st.dataframe(account_hedge_stats)

            unique_users = set(hedge_df['user_1']).union(set(hedge_df['user_2']))
            hedge_user_percentage = (len(unique_users) / df['user_id'].nunique()) * 100
            hedge_account_percentage = (len(set(hedge_df['account_1']).union(set(hedge_df['account_2']))) / df['account_id'].nunique()) * 100

            st.metric(label="% of Users Involved in Hedging", value=f"{hedge_user_percentage:.2f}%")
            st.metric(label="% of Accounts Involved in Hedging", value=f"{hedge_account_percentage:.2f}%")
        else:
            st.warning("No hedging activity detected with current parameters.")

    except pd.errors.EmptyDataError:
        st.error("❌ The uploaded file is empty or malformed. Please upload a valid CSV.")
    except Exception as e:
        st.error(f"❌ An unexpected error occurred: {e}")
else:
    st.info("Please upload a CSV file to begin analysis.")
