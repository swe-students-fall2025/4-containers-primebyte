// Update current status
function updateCurrentStatus() {
    fetch('/api/current')
        .then(response => response.json())
        .then(data => {
            const levelElement = document.getElementById('current-noise-level');
            const decibelElement = document.getElementById('current-decibels');
            const updatedElement = document.getElementById('last-updated');
            
            if (levelElement && decibelElement && updatedElement) {
                levelElement.textContent = data.noise_level.toUpperCase();
                levelElement.className = 'noise-level ' + data.noise_level.toLowerCase();
                decibelElement.textContent = data.decibels.toFixed(1) + ' dB';
                updatedElement.textContent = 'Last updated: ' + 
                    new Date(data.timestamp).toLocaleString();
            }
        })
        .catch(error => {
            console.error('Error fetching current status:', error);
        });
}

// Update statistics
function updateStatistics() {
    fetch('/api/stats')
        .then(response => response.json())
        .then(data => {
            const avgDbElement = document.getElementById('avg-db');
            const maxDbElement = document.getElementById('max-db');
            const minDbElement = document.getElementById('min-db');
            const noiseLevelElement = document.getElementById('noise-level');
            
            if (avgDbElement) avgDbElement.textContent = data.average_db.toFixed(1);
            if (maxDbElement) maxDbElement.textContent = data.max_db.toFixed(1);
            if (minDbElement) minDbElement.textContent = data.min_db.toFixed(1);
            
            if (noiseLevelElement) {
                noiseLevelElement.textContent = data.noise_level.toUpperCase();
                noiseLevelElement.className = 'noise-level ' + data.noise_level.toLowerCase().replace(' ', '-');
            }
        })
        .catch(error => {
            console.error('Error fetching statistics:', error);
        });
}

// Initialize charts (placeholder - will be implemented in later tasks)
function initializeCharts() {
    console.log('Charts will be initialized when backend APIs are ready');
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