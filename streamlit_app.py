import streamlit as st
import pandas as pd
import numpy as np
import json
import os
from datetime import datetime
import re

# Set page configuration
st.set_page_config(page_title="Hedge Detection Tool", layout="wide")

st.title("Hedge Detection Analysis Tool")
st.markdown("Upload a CSV file with trading data to identify potential hedge pairs")

# Sidebar for configuration parameters
st.sidebar.header("Analysis Parameters")
price_threshold = st.sidebar.slider("Price Threshold ($)", min_value=0.1, max_value=20.0, value=5.0, step=0.1)
confidence_threshold = st.sidebar.slider("Confidence Threshold", min_value=0.1, max_value=1.0, value=0.7, step=0.05)
include_close_price = st.sidebar.checkbox("Include Close Price in Analysis", value=True)

# File upload widget
uploaded_file = st.file_uploader("Choose a CSV file", type=["csv"])

# Functions from the original app, now included directly
def normalize_asset_name(asset):
    """Normalize asset names (e.g., treat NQM5 and MNQM5 as equivalent)"""
    # Remove any non-alphanumeric characters
    asset = re.sub(r'[^a-zA-Z0-9]', '', asset)
    
    # Basic normalization rules
    if 'NQ' in asset.upper():
        return 'NQ'
    if 'ES' in asset.upper():
        return 'ES'
    if 'CL' in asset.upper():
        return 'CL'
    
    return asset

def parse_list_field(field):
    """Parse list fields from string representation"""
    if isinstance(field, str):
        # Remove brackets and split by comma
        field = field.strip('[]').split(',')
        # Convert to float if possible
        try:
            return [float(x.strip()) for x in field if x.strip()]
        except ValueError:
            return [x.strip() for x in field if x.strip()]
    return field

def calculate_confidence_score(trade1, trade2, price_diff, price_threshold, time_overlap, include_close_price):
    """Calculate confidence score based on how well the pair matches hedging criteria"""
    score = 0
    
    # Price similarity (closer prices = higher score)
    score += 0.4 * (1 - price_diff / price_threshold)
    
    # Time overlap
    score += 0.3
    
    # If including close prices in matching
    if include_close_price:
        close_price_diff = abs(float(trade1['avg_market_close']) - float(trade2['avg_market_close']))
        
        # Close price similarity (closer prices = higher score)
        score += 0.3 * (1 - min(close_price_diff / price_threshold, 1))
    else:
        # If not considering close prices, distribute the weight elsewhere
        score += 0.15  # Add half of the potential close price score as a baseline
    
    # Quantity similarity (optional bonus)
    qty1 = float(trade1['total_contracts'])
    qty2 = float(trade2['total_contracts'])
    if qty1 == qty2:
        score += 0.1
    
    return min(max(score, 0), 1)  # Ensure score is between 0 and 1

def find_notable_patterns(hedge_pairs, df):
    """Find notable patterns in the hedge pairs"""
    if not hedge_pairs:
        return {
            'frequent_users': [],
            'peak_hours': [],
            'asset_distribution': []
        }
    
    # Find users with multiple hedge pairs
    user_hedge_counts = {}
    for pair in hedge_pairs:
        user1 = pair['trade1']['user_id']
        user2 = pair['trade2']['user_id']
        
        user_hedge_counts[user1] = user_hedge_counts.get(user1, 0) + 1
        if user1 != user2:
            user_hedge_counts[user2] = user_hedge_counts.get(user2, 0) + 1
    
    # Find users with high hedge counts
    frequent_users = [
        {'user_id': user_id, 'count': count}
        for user_id, count in user_hedge_counts.items()
        if count >= 3
    ]
    frequent_users.sort(key=lambda x: x['count'], reverse=True)
    
    # Check for time patterns (e.g., same time of day)
    hour_patterns = {}
    for pair in hedge_pairs:
        # Convert timestamp to datetime
        entry_time = datetime.strptime(pair['trade1']['entry_time'], '%Y-%m-%d %H:%M:%S')
        hour = entry_time.hour
        
        hour_patterns[hour] = hour_patterns.get(hour, 0) + 1
    
    # Find peak hours (hours with at least 80% of the max count)
    max_hour_count = max(hour_patterns.values()) if hour_patterns else 0
    peak_hours = [
        {'hour': hour, 'count': count, 'percentage': count / len(hedge_pairs) * 100}
        for hour, count in hour_patterns.items()
        if count >= max_hour_count * 0.8
    ]
    peak_hours.sort(key=lambda x: x['count'], reverse=True)
    
    # Check for asset patterns
    asset_patterns = {}
    for pair in hedge_pairs:
        asset = pair['asset']
        asset_patterns[asset] = asset_patterns.get(asset, 0) + 1
    
    asset_distribution = [
        {'asset': asset, 'count': count, 'percentage': count / len(hedge_pairs) * 100}
        for asset, count in asset_patterns.items()
    ]
    asset_distribution.sort(key=lambda x: x['count'], reverse=True)
    
    return {
        'frequent_users': frequent_users,
        'peak_hours': peak_hours,
        'asset_distribution': asset_distribution
    }

# Original function for finding hedge pairs
def find_hedge_pairs(df, price_threshold, confidence_threshold, include_close_price):
    """Find potential hedge pairs in the trading data"""
    # Clean data - ensure required columns exist
    required_columns = ['tradehash', 'short_long', 'asset', 'entry_datetimes', 
                        'market_entries', 'close_datetimes', 'market_closes', 
                        'account_id', 'user_id', 'net_profit', 'total_contracts']
    
    for col in required_columns:
        if col not in df.columns:
            st.error(f"Required column '{col}' not found in CSV")
            return []
    
    # Clean data - remove rows with missing essential values
    df = df.dropna(subset=required_columns)
    
    # Normalize asset names
    df['normalized_asset'] = df['asset'].apply(normalize_asset_name)
    
    # Parse list fields
    df['entry_datetimes_parsed'] = df['entry_datetimes'].apply(parse_list_field)
    df['close_datetimes_parsed'] = df['close_datetimes'].apply(parse_list_field)
    df['market_entries_parsed'] = df['market_entries'].apply(parse_list_field)
    df['market_closes_parsed'] = df['market_closes'].apply(parse_list_field)
    
    # Extract first entry and close times as numeric values
    df['entry_time'] = df['entry_datetimes_parsed'].apply(lambda x: float(x[0]) if isinstance(x, list) and len(x) > 0 else None)
    df['close_time'] = df['close_datetimes_parsed'].apply(lambda x: float(x[0]) if isinstance(x, list) and len(x) > 0 else None)
    
    # Convert avg_market_entry and avg_market_close to float if they're not already
    df['avg_market_entry'] = pd.to_numeric(df['avg_market_entry'], errors='coerce')
    df['avg_market_close'] = pd.to_numeric(df['avg_market_close'], errors='coerce')
    
    # Group trades by normalized asset
    hedge_pairs = []
    pair_id = 1
    
    # Progress bar for Streamlit
    progress_text = "Analyzing trades for potential hedge pairs..."
    progress_bar = st.progress(0)
    
    # Group by normalized asset
    asset_groups = df.groupby('normalized_asset')
    total_groups = len(asset_groups)
    
    for i, (asset, group) in enumerate(asset_groups):
        trades = group.to_dict('records')
        
        for j in range(len(trades)):
            trade1 = trades[j]
            
            # Skip if entry or close time is missing
            if pd.isna(trade1['entry_time']) or pd.isna(trade1['close_time']):
                continue
                
            for k in range(j + 1, len(trades)):
                trade2 = trades[k]
                
                # Skip if entry or close time is missing
                if pd.isna(trade2['entry_time']) or pd.isna(trade2['close_time']):
                    continue
                
                # Check if trades have opposite directions
                if trade1['short_long'] != trade2['short_long']:
                    # Check if one is LONG and the other is SHORT
                    if set([trade1['short_long'], trade2['short_long']]) == set(['LONG', 'SHORT']):
                        # Check if entry prices are within threshold
                        price_diff = abs(float(trade1['avg_market_entry']) - float(trade2['avg_market_entry']))
                        
                        if price_diff <= price_threshold:
                            # Check if timeframes overlap
                            time_overlap = ((trade2['entry_time'] >= trade1['entry_time'] and 
                                            trade2['entry_time'] <= trade1['close_time']) or 
                                           (trade1['entry_time'] >= trade2['entry_time'] and 
                                            trade1['entry_time'] <= trade2['close_time']))
                            
                            if time_overlap:
                                # Calculate confidence score
                                confidence_score = calculate_confidence_score(
                                    trade1, trade2, price_diff, price_threshold, 
                                    time_overlap, include_close_price
                                )
                                
                                # Only include pairs with confidence above threshold
                                if confidence_score >= confidence_threshold:
                                    # Determine hedge type
                                    hedge_type = 'self_hedge' if trade1['user_id'] == trade2['user_id'] else 'inter_user_hedge'
                                    
                                    # Format entry and close times for display
                                    entry_time1 = datetime.fromtimestamp(trade1['entry_time']/1000).strftime('%Y-%m-%d %H:%M:%S')
                                    close_time1 = datetime.fromtimestamp(trade1['close_time']/1000).strftime('%Y-%m-%d %H:%M:%S')
                                    entry_time2 = datetime.fromtimestamp(trade2['entry_time']/1000).strftime('%Y-%m-%d %H:%M:%S')
                                    close_time2 = datetime.fromtimestamp(trade2['close_time']/1000).strftime('%Y-%m-%d %H:%M:%S')
                                    
                                    # Create hedge pair object
                                    hedge_pair = {
                                        'id': pair_id,
                                        'type': hedge_type,
                                        'asset': asset,
                                        'trade1': {
                                            'tradehash': trade1['tradehash'],
                                            'direction': trade1['short_long'],
                                            'entry_time': entry_time1,
                                            'close_time': close_time1,
                                            'entry_price': float(trade1['avg_market_entry']),
                                            'close_price': float(trade1['avg_market_close']),
                                            'net_profit': float(trade1['net_profit']),
                                            'user_id': trade1['user_id'],
                                            'account_id': trade1['account_id'],
                                            'quantity': float(trade1['total_contracts'])
                                        },
                                        'trade2': {
                                            'tradehash': trade2['tradehash'],
                                            'direction': trade2['short_long'],
                                            'entry_time': entry_time2,
                                            'close_time': close_time2,
                                            'entry_price': float(trade2['avg_market_entry']),
                                            'close_price': float(trade2['avg_market_close']),
                                            'net_profit': float(trade2['net_profit']),
                                            'user_id': trade2['user_id'],
                                            'account_id': trade2['account_id'],
                                            'quantity': float(trade2['total_contracts'])
                                        },
                                        'entry_price_diff': price_diff,
                                        'confidence': confidence_score,
                                        'net_profit': float(trade1['net_profit']) + float(trade2['net_profit'])
                                    }
                                    
                                    hedge_pairs.append(hedge_pair)
                                    pair_id += 1
        
        # Update progress bar
        progress_bar.progress((i + 1) / total_groups)
    
    progress_bar.empty()
    return hedge_pairs

def generate_summary_stats(hedge_pairs, df):
    """Generate summary statistics for the detected hedge pairs"""
    if not hedge_pairs:
        return {
            'total_hedges': 0,
            'self_hedges': 0,
            'inter_user_hedges': 0,
            'avg_confidence': 0,
            'users_involved': 0,
            'accounts_involved': 0,
            'users_percentage': 0,
            'accounts_percentage': 0
        }
    
    # Count hedge types
    self_hedges = sum(1 for pair in hedge_pairs if pair['type'] == 'self_hedge')
    inter_user_hedges = len(hedge_pairs) - self_hedges
    
    # Calculate average confidence
    avg_confidence = sum(pair['confidence'] for pair in hedge_pairs) / len(hedge_pairs)
    
    # Count unique users and accounts involved
    unique_users = set()
    unique_accounts = set()
    
    for pair in hedge_pairs:
        unique_users.add(pair['trade1']['user_id'])
        unique_users.add(pair['trade2']['user_id'])
        unique_accounts.add(pair['trade1']['account_id'])
        unique_accounts.add(pair['trade2']['account_id'])
    
    # Calculate percentages
    total_users = df['user_id'].nunique()
    total_accounts = df['account_id'].nunique()
    
    users_percentage = (len(unique_users) / total_users * 100) if total_users > 0 else 0
    accounts_percentage = (len(unique_accounts) / total_accounts * 100) if total_accounts > 0 else 0
    
    return {
        'total_hedges': len(hedge_pairs),
        'self_hedges': self_hedges,
        'inter_user_hedges': inter_user_hedges,
        'avg_confidence': avg_confidence,
        'users_involved': len(unique_users),
        'accounts_involved': len(unique_accounts),
        'users_percentage': users_percentage,
        'accounts_percentage': accounts_percentage
    }

# Process uploaded file
if uploaded_file is not None:
    with st.spinner('Processing CSV file...'):
        try:
            df = pd.read_csv(uploaded_file)
            st.success(f"File loaded successfully with {len(df)} rows")
            
            # Show a sample of the data
            st.subheader("Data Preview")
            st.dataframe(df.head(5))
            
            # Run analysis
            if st.button("Run Hedge Analysis"):
                with st.spinner('Analyzing data for hedge pairs...'):
                    # Process data to find hedge pairs
                    hedge_pairs = find_hedge_pairs(df, price_threshold, confidence_threshold, include_close_price)
                    
                    # Generate summary statistics
                    summary_stats = generate_summary_stats(hedge_pairs, df)
                    
                    # Find notable patterns
                    notable_patterns = find_notable_patterns(hedge_pairs, df)
                    
                    # Display results
                    st.header("Analysis Results")
                    
                    # Summary stats
                    st.subheader("Summary Statistics")
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Total Hedge Pairs", summary_stats['total_hedges'])
                    col2.metric("Self Hedges", summary_stats['self_hedges'])
                    col3.metric("Inter-User Hedges", summary_stats['inter_user_hedges'])
                    col4.metric("Avg. Confidence", f"{summary_stats['avg_confidence']:.2f}")
                    
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Users Involved", summary_stats['users_involved'])
                    col2.metric("Accounts Involved", summary_stats['accounts_involved'])
                    col3.metric("Users %", f"{summary_stats['users_percentage']:.1f}%")
                    col4.metric("Accounts %", f"{summary_stats['accounts_percentage']:.1f}%")
                    
                    # Notable patterns
                    st.subheader("Notable Patterns")
                    
                    # Asset distribution
                    if notable_patterns['asset_distribution']:
                        st.write("Asset Distribution:")
                        asset_df = pd.DataFrame(notable_patterns['asset_distribution'])
                        st.bar_chart(asset_df.set_index('asset')['count'])
                        st.dataframe(asset_df)
                    
                    # Peak hours
                    if notable_patterns['peak_hours']:
                        st.write("Peak Hours:")
                        hours_df = pd.DataFrame(notable_patterns['peak_hours'])
                        st.bar_chart(hours_df.set_index('hour')['count'])
                        st.dataframe(hours_df)
                    
                    # Frequent users
                    if notable_patterns['frequent_users']:
                        st.write("Frequent Users:")
                        users_df = pd.DataFrame(notable_patterns['frequent_users'])
                        st.dataframe(users_df)
                    
                    # Hedge pairs table
                    st.subheader("Detected Hedge Pairs")
                    if hedge_pairs:
                        # Convert to a more Streamlit-friendly format
                        pairs_for_display = []
                        for pair in hedge_pairs:
                            pairs_for_display.append({
                                'ID': pair['id'],
                                'Type': pair['type'],
                                'Asset': pair['asset'],
                                'User 1': pair['trade1']['user_id'],
                                'Direction 1': pair['trade1']['direction'],
                                'User 2': pair['trade2']['user_id'],
                                'Direction 2': pair['trade2']['direction'],
                                'Entry Price Diff': f"${pair['entry_price_diff']:.2f}",
                                'Confidence': f"{pair['confidence']:.2f}",
                                'Net Profit': f"${pair['net_profit']:.2f}"
                            })
                        
                        pairs_df = pd.DataFrame(pairs_for_display)
                        st.dataframe(pairs_df)
                        
                        # Export options
                        csv = pairs_df.to_csv(index=False)
                        st.download_button(
                            label="Download Hedge Pairs CSV",
                            data=csv,
                            file_name="hedge_pairs.csv",
                            mime="text/csv"
                        )
                        
                        # Detailed view for selected pair
                        st.subheader("Pair Details")
                        pair_id = st.selectbox("Select Pair ID to View Details", options=[p['id'] for p in hedge_pairs])
                        
                        selected_pair = next((p for p in hedge_pairs if p['id'] == pair_id), None)
                        if selected_pair:
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.write("Trade 1")
                                st.json(selected_pair['trade1'])
                            
                            with col2:
                                st.write("Trade 2")
                                st.json(selected_pair['trade2'])
                    else:
                        st.info("No hedge pairs detected with the current parameters. Try adjusting the thresholds.")
                        
        except Exception as e:
            st.error(f"Error processing file: {str(e)}")
else:
    st.info("Please upload a CSV file to begin analysis")
    
# Footer
st.markdown("---")
st.markdown("Hedge Detection Tool © 2023") 
