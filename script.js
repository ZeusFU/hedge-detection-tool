// Global variables
let uploadedData = null;
let hedgePairs = [];
let currentPage = 1;
const pageSize = 10;

// DOM Elements
document.addEventListener('DOMContentLoaded', function() {
    // File upload handling
    const dropArea = document.getElementById('drop-area');
    const fileInput = document.getElementById('fileInput');
    const fileInfo = document.getElementById('file-info');
    const fileName = document.getElementById('file-name');
    const removeFileBtn = document.getElementById('remove-file');
    const analyzeBtn = document.getElementById('analyze-button');
    
    // Parameters
    const priceThreshold = document.getElementById('price-threshold');
    const confidenceThreshold = document.getElementById('confidence-threshold');
    const includeClosePrice = document.getElementById('include-close-price');
    
    // Results sections
    const loadingSection = document.getElementById('loading-section');
    const resultsSection = document.getElementById('results-section');
    
    // Filters
    const filterType = document.getElementById('filter-type');
    const filterConfidence = document.getElementById('filter-confidence');
    const confidenceValue = document.getElementById('confidence-value');
    const sortBy = document.getElementById('sort-by');
    
    // Pagination
    const prevPageBtn = document.getElementById('prev-page');
    const nextPageBtn = document.getElementById('next-page');
    const pageInfo = document.getElementById('page-info');
    
    // Export buttons
    const exportCsvBtn = document.getElementById('export-csv');
    const exportJsonBtn = document.getElementById('export-json');
    const exportPdfBtn = document.getElementById('export-pdf');
    
    // Modal
    const modal = document.getElementById('pair-details-modal');
    const closeModal = document.querySelector('.close-modal');
    
    // Event Listeners for drag and drop
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, preventDefaults, false);
    });
    
    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }
    
    ['dragenter', 'dragover'].forEach(eventName => {
        dropArea.addEventListener(eventName, highlight, false);
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, unhighlight, false);
    });
    
    function highlight() {
        dropArea.classList.add('highlight');
    }
    
    function unhighlight() {
        dropArea.classList.remove('highlight');
    }
    
    // Handle file drop
    dropArea.addEventListener('drop', handleDrop, false);
    
    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        
        if (files.length) {
            handleFiles(files);
        }
    }
    
    // Handle file selection via button
    fileInput.addEventListener('change', function() {
        if (this.files.length) {
            handleFiles(this.files);
        }
    });
    
    function handleFiles(files) {
        const file = files[0];
        if (file.type === 'text/csv' || file.name.endsWith('.csv')) {
            fileName.textContent = file.name;
            fileInfo.style.display = 'flex';
            analyzeBtn.disabled = false;
            
            // Parse the CSV file
            Papa.parse(file, {
                header: true,
                dynamicTyping: true,
                complete: function(results) {
                    uploadedData = results.data;
                    console.log('CSV data loaded:', uploadedData.length, 'rows');
                }
            });
        } else {
            alert('Please upload a CSV file.');
        }
    }
    
    // Remove file button
    removeFileBtn.addEventListener('click', function() {
        fileInput.value = '';
        fileInfo.style.display = 'none';
        analyzeBtn.disabled = true;
        uploadedData = null;
    });
    
    // Update confidence value display
    filterConfidence.addEventListener('input', function() {
        confidenceValue.textContent = this.value;
    });
    
    // Analyze button
    analyzeBtn.addEventListener('click', function() {
        if (!uploadedData) {
            alert('Please upload a CSV file first.');
            return;
        }
        
        // Show loading section
        loadingSection.style.display = 'block';
        resultsSection.style.display = 'none';
        
        // Get parameters
        const priceThresholdValue = parseFloat(priceThreshold.value);
        const confidenceThresholdValue = parseFloat(confidenceThreshold.value);
        const includeClosePriceValue = includeClosePrice.checked;
        
        // Process data (this would normally be done on the backend)
        setTimeout(() => {
            processData(uploadedData, priceThresholdValue, confidenceThresholdValue, includeClosePriceValue);
            
            // Hide loading, show results
            loadingSection.style.display = 'none';
            resultsSection.style.display = 'block';
            
            // Scroll to results
            resultsSection.scrollIntoView({ behavior: 'smooth' });
        }, 1500); // Simulating processing time
    });
    
    // Filter and sort event listeners
    filterType.addEventListener('change', updateResults);
    filterConfidence.addEventListener('change', updateResults);
    sortBy.addEventListener('change', updateResults);
    
    // Pagination event listeners
    prevPageBtn.addEventListener('click', () => {
        if (currentPage > 1) {
            currentPage--;
            updateResults();
        }
    });
    
    nextPageBtn.addEventListener('click', () => {
        const totalPages = Math.ceil(getFilteredHedgePairs().length / pageSize);
        if (currentPage < totalPages) {
            currentPage++;
            updateResults();
        }
    });
    
    // Export buttons
    exportCsvBtn.addEventListener('click', exportToCsv);
    exportJsonBtn.addEventListener('click', exportToJson);
    exportPdfBtn.addEventListener('click', exportToPdf);
    
    // Modal close button
    closeModal.addEventListener('click', () => {
        modal.style.display = 'none';
    });
    
    // Close modal when clicking outside
    window.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.style.display = 'none';
        }
    });
});

// Process the uploaded data to find hedge pairs
function processData(data, priceThreshold, confidenceThreshold, includeClosePrice) {
    // Reset results
    hedgePairs = [];
    
    // Clean data - remove any rows with missing essential values
    const cleanData = data.filter(row => 
        row && row.tradehash && row.short_long && row.asset && 
        row.entry_datetimes && row.market_entries && 
        row.close_datetimes && row.market_closes &&
        row.account_id && row.user_id
    );
    
    // Group trades by asset (treating equivalent assets as the same)
    const assetGroups = {};
    cleanData.forEach(trade => {
        // Normalize asset name (e.g., treat NQM5 and MNQM5 as equivalent)
        const normalizedAsset = normalizeAssetName(trade.asset);
        
        if (!assetGroups[normalizedAsset]) {
            assetGroups[normalizedAsset] = [];
        }
        assetGroups[normalizedAsset].push(trade);
    });
    
    // Find potential hedge pairs
    let pairId = 1;
    Object.keys(assetGroups).forEach(asset => {
        const trades = assetGroups[asset];
        
        for (let i = 0; i < trades.length; i++) {
            const trade1 = trades[i];
            
            // Parse entry and close times
            const entry1 = parseFloat(trade1.entry_datetimes.replace('[', '').replace(']', ''));
            const close1 = parseFloat(trade1.close_datetimes.replace('[', '').replace(']', ''));
            
            for (let j = i + 1; j < trades.length; j++) {
                const trade2 = trades[j];
                
                // Check if trades have opposite directions
                if (trade1.short_long !== trade2.short_long) {
                    // Parse entry and close times
                    const entry2 = parseFloat(trade2.entry_datetimes.replace('[', '').replace(']', ''));
                    const close2 = parseFloat(trade2.close_datetimes.replace('[', '').replace(']', ''));
                    
                    // Parse entry prices
                    const price1 = parseFloat(trade1.avg_market_entry);
                    const price2 = parseFloat(trade2.avg_market_entry);
                    
                    // Check if entry prices are within threshold
                    const priceDiff = Math.abs(price1 - price2);
                    if (priceDiff <= priceThreshold) {
                        // Check if timeframes overlap
                        const timeOverlap = (entry2 >= entry1 && entry2 <= close1) || 
                                           (entry1 >= entry2 && entry1 <= close2);
                        
                        if (timeOverlap) {
                            // Calculate confidence score
                            let confidenceScore = calculateConfidenceScore(
                                trade1, trade2, priceDiff, priceThreshold, 
                                timeOverlap, includeClosePrice
                            );
                            
                            // Only include pairs with confidence above threshold
                            if (confidenceScore >= confidenceThreshold) {
                                // Determine hedge type
                                const hedgeType = trade1.user_id === trade2.user_id ? 
                                    'self_hedge' : 'inter_user_hedge';
                                
                                // Create hedge pair object
                                const hedgePair = {
                                    id: pairId++,
                                    type: hedgeType,
                                    asset: asset,
                                    trade1: trade1,
                                    trade2: trade2,
                                    entryTimeDiff: Math.abs(entry1 - entry2),
                                    entryPriceDiff: priceDiff,
                                    confidence: confidenceScore,
                                    netProfit: parseFloat(trade1.net_profit) + parseFloat(trade2.net_profit)
                                };
                                
                                hedgePairs.push(hedgePair);
                            }
                        }
                    }
                }
            }
        }
    });
    
    // Update results display
    updateSummaryStats();
    createCharts();
    updateResults();
    findNotablePatterns();
}

// Normalize asset names (e.g., treat NQM5 and MNQM5 as equivalent)
function normalizeAssetName(asset) {
    // This is a simplified example - in a real application, you would have more comprehensive rules
    if (asset.includes('NQ')) {
        return 'NQ';
    }
    return asset;
}

// Calculate confidence score based on how well the pair matches hedging criteria
function calculateConfidenceScore(trade1, trade2, priceDiff, priceThreshold, timeOverlap, includeClosePrice) {
    let score = 0;
    
    // Price similarity (closer prices = higher score)
    score += 0.4 * (1 - priceDiff / priceThreshold);
    
    // Time overlap
    score += 0.3;
    
    // If including close prices in matching
    if (includeClosePrice) {
        const closePrice1 = parseFloat(trade1.avg_market_close);
        const closePrice2 = parseFloat(trade2.avg_market_close);
        const closePriceDiff = Math.abs(closePrice1 - closePrice2);
        
        // Close price similarity (closer prices = higher score)
        score += 0.3 * (1 - Math.min(closePriceDiff / priceThreshold, 1));
    } else {
        // If not considering close prices, distribute the weight elsewhere
        score += 0.15; // Add half of the potential close price score as a baseline
    }
    
    // Quantity similarity (optional bonus)
    const qty1 = parseFloat(trade1.total_contracts);
    const qty2 = parseFloat(trade2.total_contracts);
    if (qty1 === qty2) {
        score += 0.1;
    }
    
    return Math.min(Math.max(score, 0), 1); // Ensure score is between 0 and 1
}

// Get filtered hedge pairs based on current filter settings
function getFilteredHedgePairs() {
    const typeFilter = document.getElementById('filter-type').value;
    const confidenceFilter = parseFloat(document.getElementById('filter-confidence').value);
    
    return hedgePairs.filter(pair => {
        // Filter by type
        if (typeFilter !== 'all' && pair.type !== typeFilter) {
            return false;
        }
        
        // Filter by confidence
        if (pair.confidence < confidenceFilter) {
            return false;
        }
        
        return true;
    });
}

// Sort hedge pairs based on current sort settings
function getSortedHedgePairs(pairs) {
    const sortOption = document.getElementById('sort-by').value;
    
    return [...pairs].sort((a, b) => {
        switch (sortOption) {
            case 'confidence-desc':
                return b.confidence - a.confidence;
            case 'confidence-asc':
                return a.confidence - b.confidence;
            case 'time-desc':
                return parseFloat(b.trade1.entry_datetimes.replace('[', '').replace(']', '')) - 
                       parseFloat(a.trade1.entry_datetimes.replace('[', '').replace(']', ''));
            case 'time-asc':
                return parseFloat(a.trade1.entry_datetimes.replace('[', '').replace(']', '')) - 
                       parseFloat(b.trade1.entry_datetimes.replace('[', '').replace(']', ''));
            default:
                return 0;
        }
    });
}

// Update the results table based on current filters and sorting
function updateResults() {
    const filteredPairs = getFilteredHedgePairs();
    const sortedPairs = getSortedHedgePairs(filteredPairs);
    
    // Calculate pagination
    const totalPages = Math.ceil(sortedPairs.length / pageSize);
    currentPage = Math.min(currentPage, totalPages || 1);
    
    const startIndex = (currentPage - 1) * pageSize;
    const endIndex = Math.min(startIndex + pageSize, sortedPairs.length);
    const pairsToShow = sortedPairs.slice(startIndex, endIndex);
    
    // Update pagination controls
    document.getElementById('prev-page').disabled = currentPage <= 1;
    document.getElementById('next-page').disabled = currentPage >= totalPages;
    document.getElementById('page-info').textContent = `Page ${currentPage} of ${totalPages || 1}`;
    
    // Update table
    const tableBody = document.getElementById('hedge-pairs-body');
    tableBody.innerHTML = '';
    
    pairsToShow.forEach(pair => {
        const row = document.createElement('tr');
        
        // Format entry times for display
        const entryTime1 = new Date(parseInt(pair.trade1.entry_datetimes.replace('[', '').replace(']', ''))).toLocaleString();
        const entryTime2 = new Date(parseInt(pair.trade2.entry_datetimes.replace('[', '').replace(']', ''))).toLocaleString();
        
        row.innerHTML = `
            <td>${pair.id}</td>
            <td>${pair.type === 'self_hedge' ? 'Self-Hedge' : 'Inter-User Hedge'}</td>
            <td>${pair.asset}</td>
            <td>${entryTime1}<br>${entryTime2}</td>
            <td>${pair.trade1.avg_market_entry}<br>${pair.trade2.avg_market_entry}</td>
            <td>${pair.confidence.toFixed(2)}</td>
            <td>${pair.netProfit.toFixed(2)}</td>
            <td><button class="view-details" data-pair-id="${pair.id}">View</button></td>
        `;
        
        tableBody.appendChild(row);
    });
    
    // Add event listeners to view details buttons
    document.querySelectorAll('.view-details').forEach(button => {
        button.addEventListener('click', function() {
            const pairId = parseInt(this.getAttribute('data-pair-id'));
            showPairDetails(pairId);
        });
    });
}

// Update summary statistics
function updateSummaryStats() {
    // Count hedge types
    const selfHedges = hedgePairs.filter(pair => pair.type === 'self_hedge').length;
    const interUserHedges = hedgePairs.filter(pair => pair.type === 'inter_user_hedge').length;
    
    // Calculate average confidence
    const avgConfidence = hedgePairs.length > 0 ? 
        hedgePairs.reduce((sum, pair) => sum + pair.confidence, 0) / hedgePairs.length : 0;
    
    // Count unique users and accounts involved
    const uniqueUsers = new Set();
    const uniqueAccounts = new Set();
    
    hedgePairs.forEach(pair => {
        uniqueUsers.add(pair.trade1.user_id);
        uniqueUsers.add(pair.trade2.user_id);
        uniqueAccounts.add(pair.trade1.account_id);
        uniqueAccounts.add(pair.trade2.account_id);
    });
    
    // Update DOM elements
    document.getElementById('total-hedges').textContent = hedgePairs.length;
    document.getElementById('self-hedges').textContent = selfHedges;
    document.getElementById('inter-user-hedges').textContent = interUserHedges;
    document.getElementById('avg-confidence').textContent = avgConfidence.toFixed(2);
    document.getElementById('users-involved').textContent = uniqueUsers.size;
    document.getElementById('accounts-involved').textContent = uniqueAccounts.size;
}

// Create charts for visualizations
function createCharts() {
    // Hedge Types Chart
    const selfHedges = hedgePairs.filter(pair => pair.type === 'self_hedge').length;
    const interUserHedges = hedgePairs.filter(pair => pair.type === 'inter_user_hedge').length;
    
    const hedgeTypesCtx = document.getElementById('hedge-types-chart').getContext('2d');
    new Chart(hedgeTypesCtx, {
        type: 'pie',
        data: {
            labels: ['Self-Hedge', 'Inter-User Hedge'],
            datasets: [{
                data: [selfHedges, interUserHedges],
                backgroundColor: ['#3498db', '#e74c3c']
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            title: {
                display: true,
                text: 'Hedge Types Distribution'
            }
        }
    });
    
    // Confidence Distribution Chart
    const confidenceBins = [0, 0.2, 0.4, 0.6, 0.8, 1];
    const confidenceCounts = Array(5).fill(0);
    
    hedgePairs.forEach(pair => {
        for (let i = 0; i < confidenceBins.length - 1; i++) {
            if (pair.confidence >= confidenceBins[i] && pair.confidence < confidenceBins[i + 1]) {
                confidenceCounts[i]++;
                break;
            }
        }
        // Handle the case where confidence is exactly 1
        if (pair.confidence === 1) {
            confidenceCounts[4]++;
        }
    });
    
    const confidenceLabels = ['0.0-0.2', '0.2-0.4', '0.4-0.6', '0.6-0.8', '0.8-1.0'];
    
    const confidenceCtx = document.getElementById('confidence-distribution-chart').getContext('2d');
    new Chart(confidenceCtx, {
        type: 'bar',
        data: {
            labels: confidenceLabels,
            datasets: [{
                label: 'Number of Hedge Pairs',
                data: confidenceCounts,
                backgroundColor: '#2ecc71'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            title: {
                display: true,
                text: 'Confidence Score Distribution'
            },
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
    
    // Time Distribution Chart (by hour of day)
    const hourCounts = Array(24).fill(0);
    
    hedgePairs.forEach(pair => {
        const entryTime = new Date(parseInt(pair.trade1.entry_datetimes.replace('[', '').replace(']', '')));
        const hour = entryTime.getHours();
        hourCounts[hour]++;
    });
    
    const hourLabels = Array.from({length: 24}, (_, i) => `${i}:00`);
    
    const timeCtx = document.getElementById('time-distribution-chart').getContext('2d');
    new Chart(timeCtx, {
        type: 'line',
        data: {
            labels: hourLabels,
            datasets: [{
                label: 'Hedge Pairs by Hour',
                data: hourCounts,
                borderColor: '#9b59b6',
                backgroundColor: 'rgba(155, 89, 182, 0.2)',
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            title: {
                display: true,
                text: 'Hedge Pairs by Hour of Day'
            },
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
}

// Find notable patterns in the hedge pairs
function findNotablePatterns() {
    const notableFindings = document.getElementById('notable-findings-content');
    notableFindings.innerHTML = '';
    
    if (hedgePairs.length === 0) {
        notableFindings.innerHTML = '<p>No hedge pairs detected.</p>';
        return;
    }
    
    // Find users with multiple hedge pairs
    const userHedgeCounts = {};
    hedgePairs.forEach(pair => {
        const user1 = pair.trade1.user_id;
        const user2 = pair.trade2.user_id;
        
        userHedgeCounts[user1] = (userHedgeCounts[user1] || 0) + 1;
        if (user1 !== user2) {
            userHedgeCounts[user2] = (userHedgeCounts[user2] || 0) + 1;
        }
    });
    
    // Find users with high hedge counts
    const frequentUsers = Object.entries(userHedgeCounts)
        .filter(([_, count]) => count >= 3)
        .sort((a, b) => b[1] - a[1]);
    
    if (frequentUsers.length > 0) {
        const usersList = document.createElement('div');
        usersList.innerHTML = '<h4>Users with Multiple Hedge Pairs:</h4><ul>';
        
        frequentUsers.forEach(([userId, count]) => {
            usersList.innerHTML += `<li>User ${userId}: ${count} hedge pairs</li>`;
        });
        
        usersList.innerHTML += '</ul>';
        notableFindings.appendChild(usersList);
    }
    
    // Check for time patterns (e.g., same time of day)
    const hourPatterns = {};
    hedgePairs.forEach(pair => {
        const entryTime = new Date(parseInt(pair.trade1.entry_datetimes.replace('[', '').replace(']', '')));
        const hour = entryTime.getHours();
        
        hourPatterns[hour] = (hourPatterns[hour] || 0) + 1;
    });
    
    const peakHours = Object.entries(hourPatterns)
        .filter(([_, count]) => count >= Math.max(...Object.values(hourPatterns)) * 0.8)
        .sort((a, b) => b[1] - a[1]);
    
    if (peakHours.length > 0) {
        const timePatternDiv = document.createElement('div');
        timePatternDiv.innerHTML = '<h4>Peak Hedging Hours:</h4><ul>';
        
        peakHours.forEach(([hour, count]) => {
            timePatternDiv.innerHTML += `<li>${hour}:00 - ${hour}:59: ${count} hedge pairs (${(count / hedgePairs.length * 100).toFixed(1)}% of total)</li>`;
        });
        
        timePatternDiv.innerHTML += '</ul>';
        notableFindings.appendChild(timePatternDiv);
    }
    
    // Check for asset patterns
    const assetPatterns = {};
    hedgePairs.forEach(pair => {
        assetPatterns[pair.asset] = (assetPatterns[pair.asset] || 0) + 1;
    });
    
    const assetList = document.createElement('div');
    assetList.innerHTML = '<h4>Hedge Pairs by Asset:</h4><ul>';
    
    Object.entries(assetPatterns)
        .sort((a, b) => b[1] - a[1])
        .forEach(([asset, count]) => {
            assetList.innerHTML += `<li>${asset}: ${count} hedge pairs (${(count / hedgePairs.length * 100).toFixed(1)}% of total)</li>`;
        });
    
    assetList.innerHTML += '</ul>';
    notableFindings.appendChild(assetList);
}

// Show detailed information about a specific hedge pair
function showPairDetails(pairId) {
    const pair = hedgePairs.find(p => p.id === pairId);
    if (!pair) return;
    
    const modal = document.getElementById('pair-details-modal');
    const content = document.getElementById('pair-details-content');
    
    // Format dates for display
    const entryTime1 = new Date(parseInt(pair.trade1.entry_datetimes.replace('[', '').replace(']', ''))).toLocaleString();
    const closeTime1 = new Date(parseInt(pair.trade1.close_datetimes.replace('[', '').replace(']', ''))).toLocaleString();
    const entryTime2 = new Date(parseInt(pair.trade2.entry_datetimes.replace('[', '').replace(']', ''))).toLocaleString();
    const closeTime2 = new Date(parseInt(pair.trade2.close_datetimes.replace('[', '').replace(']', ''))).toLocaleString();
    
    content.innerHTML = `
        <div class="pair-details">
            <div class="pair-summary">
                <h3>Hedge Pair #${pair.id} - ${pair.asset}</h3>
                <p><strong>Type:</strong> ${pair.type === 'self_hedge' ? 'Self-Hedge' : 'Inter-User Hedge'}</p>
                <p><strong>Confidence Score:</strong> ${pair.confidence.toFixed(2)}</p>
                <p><strong>Net Profit:</strong> $${pair.netProfit.toFixed(2)}</p>
            </div>
            
            <div class="trade-comparison">
                <h3>Trade Comparison</h3>
                <table class="comparison-table">
                    <thead>
                        <tr>
                            <th>Attribute</th>
                            <th>Trade 1</th>
                            <th>Trade 2</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>Direction</td>
                            <td>${pair.trade1.short_long}</td>
                            <td>${pair.trade2.short_long}</td>
                        </tr>
                        <tr>
                            <td>Entry Time</td>
                            <td>${entryTime1}</td>
                            <td>${entryTime2}</td>
                        </tr>
                        <tr>
                            <td>Close Time</td>
                            <td>${closeTime1}</td>
                            <td>${closeTime2}</td>
                        </tr>
                        <tr>
                            <td>Duration (seconds)</td>
                            <td>${pair.trade1.seconds_held}</td>
                            <td>${pair.trade2.seconds_held}</td>
                        </tr>
                        <tr>
                            <td>Entry Price</td>
                            <td>${pair.trade1.avg_market_entry}</td>
                            <td>${pair.trade2.avg_market_entry}</td>
                        </tr>
                        <tr>
                            <td>Close Price</td>
                            <td>${pair.trade1.avg_market_close}</td>
                            <td>${pair.trade2.avg_market_close}</td>
                        </tr>
                        <tr>
                            <td>Quantity</td>
                            <td>${pair.trade1.total_contracts}</td>
                            <td>${pair.trade2.total_contracts}</td>
                        </tr>
                        <tr>
                            <td>Profit/Loss</td>
                            <td>$${parseFloat(pair.trade1.net_profit).toFixed(2)}</td>
                            <td>$${parseFloat(pair.trade2.net_profit).toFixed(2)}</td>
                        </tr>
                        <tr>
                            <td>User ID</td>
                            <td>${pair.trade1.user_id}</td>
                            <td>${pair.trade2.user_id}</td>
                        </tr>
                        <tr>
                            <td>Account ID</td>
                            <td>${pair.trade1.account_id}</td>
                            <td>${pair.trade2.account_id}</td>
                        </tr>
                    </tbody>
                </table>
            </div>
            
            <div class="confidence-breakdown">
                <h3>Confidence Score Breakdown</h3>
                <p>The confidence score is calculated based on how well this pair matches the hedging criteria:</p>
                <ul>
                    <li>Opposite directions: ${pair.trade1.short_long !== pair.trade2.short_long ? 'Yes' : 'No'}</li>
                    <li>Entry price difference: $${pair.entryPriceDiff.toFixed(2)}</li>
                    <li>Time overlap: Yes</li>
                    <li>Same asset: Yes</li>
                </ul>
            </div>
        </div>
    `;
    
    modal.style.display = 'block';
}

// Export functions
function exportToCsv() {
    if (hedgePairs.length === 0) {
        alert('No data to export.');
        return;
    }
    
    let csvContent = 'data:text/csv;charset=utf-8,';
    csvContent += 'Pair ID,Type,Asset,Entry Time 1,Entry Time 2,Entry Price 1,Entry Price 2,Confidence,Net Profit,User ID 1,User ID 2,Account ID 1,Account ID 2\n';
    
    hedgePairs.forEach(pair => {
        const entryTime1 = new Date(parseInt(pair.trade1.entry_datetimes.replace('[', '').replace(']', ''))).toLocaleString();
        const entryTime2 = new Date(parseInt(pair.trade2.entry_datetimes.replace('[', '').replace(']', ''))).toLocaleString();
        
        csvContent += `${pair.id},${pair.type},${pair.asset},${entryTime1},${entryTime2},${pair.trade1.avg_market_entry},${pair.trade2.avg_market_entry},${pair.confidence.toFixed(2)},${pair.netProfit.toFixed(2)},${pair.trade1.user_id},${pair.trade2.user_id},${pair.trade1.account_id},${pair.trade2.account_id}\n`;
    });
    
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', 'hedge_pairs_export.csv');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

function exportToJson() {
    if (hedgePairs.length === 0) {
        alert('No data to export.');
        return;
    }
    
    const jsonData = JSON.stringify(hedgePairs, null, 2);
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(jsonData);
    
    const link = document.createElement('a');
    link.setAttribute('href', dataStr);
    link.setAttribute('download', 'hedge_pairs_export.json');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

function exportToPdf() {
    alert('PDF export functionality would be implemented with a library like jsPDF. This is a placeholder for that functionality.');
}
