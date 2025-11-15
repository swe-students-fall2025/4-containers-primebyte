// Update current status using /api/current
function updateCurrentStatus() {
    fetch('/api/current')
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to fetch /api/current: ' + response.status);
            }
            return response.json();
        })
        .then(data => {
            const levelElement = document.getElementById('current-noise-level');
            const decibelElement = document.getElementById('current-decibels');
            const updatedElement = document.getElementById('last-updated');
            
            if (levelElement && decibelElement && updatedElement && data.noise_level) {
                const level = String(data.noise_level);
                const db = Number(data.decibels || 0);
                const ts = data.timestamp;

                levelElement.textContent = level.toUpperCase();
                levelElement.className = 'noise-level ' + level.toLowerCase();
                decibelElement.textContent = db.toFixed(1) + ' dB';
                updatedElement.textContent = 'Last updated: ' +
                    (ts ? new Date(ts).toLocaleString() : 'unknown');
            }
        })
        .catch(error => {
            console.error('Error fetching current status:', error);
        });
}

// Update statistics using /api/stats
function updateStatistics() {
    fetch('/api/stats')
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to fetch /api/stats: ' + response.status);
            }
            return response.json();
        })
        .then(data => {
            const avgDbElement = document.getElementById('avg-db');
            const maxDbElement = document.getElementById('max-db');
            const minDbElement = document.getElementById('min-db');
            const noiseLevelElement = document.getElementById('noise-level');
            
            if (avgDbElement && typeof data.average_db === 'number') {
                avgDbElement.textContent = data.average_db.toFixed(1);
            }
            if (maxDbElement && typeof data.max_db === 'number') {
                maxDbElement.textContent = data.max_db.toFixed(1);
            }
            if (minDbElement && typeof data.min_db === 'number') {
                minDbElement.textContent = data.min_db.toFixed(1);
            }

            // Derive a "dominant" noise level from data.levels (the most frequent label)
            if (noiseLevelElement && data.levels) {
                const entries = Object.entries(data.levels); // [ [label, count], ... ]
                if (entries.length > 0) {
                    let dominantLabel = entries[0][0];
                    let dominantCount = entries[0][1];

                    for (let i = 1; i < entries.length; i++) {
                        const [label, count] = entries[i];
                        if (count > dominantCount) {
                            dominantLabel = label;
                            dominantCount = count;
                        }
                    }

                    const level = String(dominantLabel || 'unknown');
                    noiseLevelElement.textContent = level.toUpperCase();
                    noiseLevelElement.className = 'noise-level ' +
                        level.toLowerCase().replace(/\s+/g, '-');
                } else {
                    noiseLevelElement.textContent = 'UNKNOWN';
                    noiseLevelElement.className = 'noise-level unknown';
                }
            }
        })
        .catch(error => {
            console.error('Error fetching statistics:', error);
        });
}

// Global variable to store chart instance
let noiseHistoryChart = null;

// Initialize noise history chart using /api/history with auto-refresh
function initializeCharts() {
    const canvas = document.getElementById('noiseHistoryChart');
    if (!canvas || typeof Chart === 'undefined') {
        console.warn('Chart.js or canvas element not available');
        return;
    }

    // Function to update chart data
    function updateChartData() {
        fetch('/api/history?limit=100')
            .then(response => {
                if (!response.ok) {
                    throw new Error('Failed to fetch /api/history: ' + response.status);
                }
                return response.json();
            })
            .then(data => {
                const timestamps = data.timestamps || [];
                const decibels = data.decibels || [];

                if (timestamps.length === 0 || decibels.length === 0) {
                    console.log('No history data available yet for chart');
                    return;
                }

                if (noiseHistoryChart) {
                    // Update existing chart
                    noiseHistoryChart.data.labels = timestamps;
                    noiseHistoryChart.data.datasets[0].data = decibels;
                    noiseHistoryChart.update('none'); // Silent update without animations
                } else {
                    // Create new chart
                    const ctx = canvas.getContext('2d');
                    noiseHistoryChart = new Chart(ctx, {
                        type: 'line',
                        data: {
                            labels: timestamps,
                            datasets: [
                                {
                                    label: 'Decibels (dB)',
                                    data: decibels,
                                    borderColor: 'rgb(75, 192, 192)',
                                    fill: false,
                                    tension: 0.1
                                }
                            ]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            scales: {
                                x: {
                                    title: {
                                        display: true,
                                        text: 'Time'
                                    }
                                },
                                y: {
                                    title: {
                                        display: true,
                                        text: 'dB'
                                    }
                                }
                            },
                            animation: {
                                duration: 0 // Disable animations for smoother updates
                            }
                        }
                    });
                }
            })
            .catch(error => {
                console.error('Error updating charts:', error);
            });
    }

    // Initial load
    updateChartData();

    // Set up auto-refresh every 5 seconds
    setInterval(updateChartData, 5000);
}

// Start periodic updates if on dashboard page
if (document.getElementById('current-noise-level')) {
    // Periodic updates
    setInterval(updateCurrentStatus, 3000); // Update every 3 seconds
    setInterval(updateStatistics, 10000);   // Update stats every 10 seconds
    
    // Initial load
    updateCurrentStatus();
    updateStatistics();
    initializeCharts();
}

// Auto-refresh for history page
if (document.getElementById("history-table")) {
    let historyRefreshInterval = null;
    
    function startHistoryAutoRefresh() {
        // Refresh history every 10 seconds
        historyRefreshInterval = setInterval(loadHistory, 10000);
        console.log('History auto-refresh started');
    }
    
    function stopHistoryAutoRefresh() {
        if (historyRefreshInterval) {
            clearInterval(historyRefreshInterval);
            historyRefreshInterval = null;
            console.log('History auto-refresh stopped');
        }
    }
    
    // Start auto-refresh when history page loads
    startHistoryAutoRefresh();
    
    // Clean up when leaving the page
    window.addEventListener('beforeunload', stopHistoryAutoRefresh);
}
