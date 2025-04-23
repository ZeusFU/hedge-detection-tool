from flask import Flask, request, jsonify, send_from_directory
import pandas as pd
import numpy as np
import json
import os
from datetime import datetime
import re

app = Flask(__name__, static_folder='.')

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/styles.css')
def styles():
    return send_from_directory('.', 'styles.css')

@app.route('/script.js')
def script():
    return send_from_directory('.', 'script.js')

@app.route('/upload-icon.svg')
def upload_icon():
    return send_from_directory('.', 'upload-icon.svg')

@app.route('/analyze', methods=['POST'])
def analyze():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if not file.filename.endswith('.csv'):
        return jsonify({'error': 'File must be a CSV'}), 400
    
    # Get parameters from request
    price_threshold = float(request.form.get('price_threshold', 5))
    confidence_threshold = float(request.form.get('confidence_threshold', 0.7))
    include_close_price = request.form.get('include_close_price', 'true').lower() == 'true'
    
    try:
        # Read CSV file
        df = pd.read_csv(file)
        
        # Process data to find hedge pairs
        hedge_pairs = find_hedge_pairs(df, price_threshold, confidence_threshold, include_close_price)
        
        # Generate summary statistics
        summary_stats = generate_summary_stats(hedge_pairs, df)
        
        # Find notable patterns
        notable_patterns = find_notable_patterns(hedge_pairs, df)
        
        return jsonify({
            'hedge_pairs': hedge_pairs,
            'summary_stats': summary_stats,
            'notable_patterns': notable_patterns
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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

def find_hedge_pairs(df, price_threshold, confidence_threshold, include_close_price):
    """Find potential hedge pairs in the trading data"""
    # Clean data - ensure required columns exist
    required_columns = ['tradehash', 'short_long', 'asset', 'entry_datetimes', 
                        'market_entries', 'close_datetimes', 'market_closes', 
                        'account_id', 'user_id', 'net_profit', 'total_contracts']
    
    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"Required column '{col}' not found in CSV")
    
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
    
    # Group by normalized asset
    for asset, group in df.groupby('normalized_asset'):
        trades = group.to_dict('records')
        
        for i in range(len(trades)):
            trade1 = trades[i]
            
            # Skip if entry or close time is missing
            if pd.isna(trade1['entry_time']) or pd.isna(trade1['close_time']):
                continue
                
            for j in range(i + 1, len(trades)):
                trade2 = trades[j]
                
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
    
    return hedge_pairs

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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
