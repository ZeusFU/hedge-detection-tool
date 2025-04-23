# Hedge Detection Website Architecture

## Overview
The Hedge Detection Website is designed to analyze trading data to identify potential hedging behavior between trades. The application will accept CSV uploads with trading data, process the data to detect hedge pairs based on specific criteria, calculate confidence scores, and present the results in an intuitive interface.

## System Components

### 1. Frontend Components
- **Upload Interface**: Allows users to upload CSV files with trading data
- **Configuration Panel**: Enables users to adjust detection parameters (optional)
- **Results Dashboard**: Displays detected hedge pairs and summary statistics
- **Visualization Components**: Charts and graphs to visualize hedge patterns
- **Export Functionality**: Options to download analysis results

### 2. Backend Components
- **File Processing Service**: Handles CSV parsing and data validation
- **Hedge Detection Engine**: Core algorithm that identifies potential hedge pairs
- **Confidence Score Calculator**: Evaluates how well pairs match hedging criteria
- **Summary Statistics Generator**: Calculates aggregate statistics on detected hedges
- **Data Export Service**: Formats results for download

### 3. Data Flow
1. User uploads CSV file through the frontend interface
2. Backend validates and processes the CSV data
3. Hedge detection algorithm analyzes trades to identify potential hedge pairs
4. Confidence scores are calculated for each pair
5. Summary statistics are generated
6. Results are sent back to the frontend for display
7. User can interact with results and export findings

## Technical Stack
- **Frontend**: HTML5, CSS3, JavaScript with modern frameworks (React)
- **Backend**: Python with Flask for web server
- **Data Processing**: Pandas for CSV handling and data manipulation
- **Visualization**: D3.js or Chart.js for interactive charts
- **Deployment**: Static site hosting for production deployment

## Hedge Detection Algorithm
The core algorithm will implement the following logic:
1. Group trades by asset (treating equivalent assets like NQM5 and MNQM5 as the same)
2. For each trade, find potential matching trades with:
   - Opposite direction (LONG vs SHORT)
   - Entry price within $5 threshold
   - Overlapping timeframes (entry of one within the duration of another)
   - Optional: similar close prices
3. Calculate confidence score based on how well pairs match criteria
4. Classify pairs as self_hedge (same user, different accounts) or inter_user_hedge (different users)
5. Track cumulative profits from each side of the hedge

## User Interface Wireframes
### Main Page
- Header with application title and brief description
- File upload section with drag-and-drop functionality
- Configuration options (collapsible)
- Results area (initially hidden, shown after processing)

### Results Dashboard
- Summary statistics panel
- Filterable table of detected hedge pairs
- Visualization section with charts showing patterns
- Export options for detailed results
