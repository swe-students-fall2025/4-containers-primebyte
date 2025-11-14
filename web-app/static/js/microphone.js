// Microphone controls - persistent across all pages
(function() {
    let audioContext;
    let mediaStream;
    let analyser;
    let dataArray;
    let isRecording = false;
    let animationId;
    let sendIntervalId; // Store interval ID for cleanup
    let smoothedDb = 0; // For exponential smoothing
    let lastUpdateTime = 0; // Throttle display updates
    let intervalMs = 5000; // Default 5 seconds, fetched on page load

    // recover microphone state from localStorage
    function loadMicrophoneState() {
        const savedState = localStorage.getItem('microphoneState');
        return savedState === 'recording';
    }

    // save to localStorage
    function saveMicrophoneState(state) {
        localStorage.setItem('microphoneState', state ? 'recording' : 'stopped');
    }

    function computeDecibels() {
        if (!analyser || !dataArray) return 0;
        analyser.getByteTimeDomainData(dataArray);

        let sumSquares = 0;
        for (let i = 0; i < dataArray.length; i++) {
            const normalized = (dataArray[i] - 128) / 128.0;
            sumSquares += normalized * normalized;
        }
        const rms = Math.sqrt(sumSquares / dataArray.length);
        
        // Logarithmic scale for realistic dB behavior
        // This prevents values from going crazy high
        const dbfs = 20 * Math.log10(rms + 0.001); // Add small offset to avoid log(0)
        // Map to realistic SPL range: -60 to -10 dbfs -> 0 to 100 dB SPL
        const rawDb = Math.max(0, Math.min(100, 70 + dbfs));
        
        // Strong exponential smoothing to prevent violent jumps
        // Alpha = 0.15 means only 15% new value, 85% old value (much smoother)
        smoothedDb = (0.15 * rawDb) + (0.85 * smoothedDb);
        
        return Number(smoothedDb.toFixed(1));
    }

    function updateRealtimeDisplay() {
        if (!isRecording) return;

        const db = computeDecibels();
        
        // Throttle display updates to every 100ms (10 times per second)
        const now = Date.now();
        if (now - lastUpdateTime < 100) {
            animationId = requestAnimationFrame(updateRealtimeDisplay);
            return;
        }
        lastUpdateTime = now;
        
        const dbDisplay = document.getElementById('realtime-db');
        
        if (dbDisplay) {
            dbDisplay.textContent = db.toFixed(1) + ' dB';
            
            // Color code based on updated thresholds
            if (db < 24) dbDisplay.style.color = '#6c757d'; // gray - silent
            else if (db < 33) dbDisplay.style.color = '#17a2b8'; // cyan - quiet
            else if (db < 50) dbDisplay.style.color = '#28a745'; // green - normal
            else if (db < 65) dbDisplay.style.color = '#ffc107'; // yellow - loud
            else dbDisplay.style.color = '#dc3545'; // red - very loud
        }

        animationId = requestAnimationFrame(updateRealtimeDisplay);
    }

    async function sendAudioData() {
        if (!isRecording) return;
        
        const db = computeDecibels();
        
        try {
            await fetch('/api/audio_data', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ decibels: db })
            });
        } catch (err) {
            console.error('Failed to send audio data:', err);
        }
    }

    async function startMicrophone() {
        try {
            audioContext = new (window.AudioContext || window.webkitAudioContext)();
            mediaStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: false,
                    noiseSuppression: false,
                    autoGainControl: false
                }
            });

            const source = audioContext.createMediaStreamSource(mediaStream);
            analyser = audioContext.createAnalyser();
            analyser.fftSize = 2048;
            analyser.smoothingTimeConstant = 0.3;
            dataArray = new Uint8Array(analyser.fftSize);
            source.connect(analyser);

            isRecording = true;
            saveMicrophoneState(true); // save state

            updateUIForRecording();

            // Start real-time display updates
            updateRealtimeDisplay();
            
            // Send audio data based on server interval configuration
            sendIntervalId = setInterval(sendAudioData, intervalMs);
            sendAudioData(); // Send immediately
        } catch (err) {
            console.error('Microphone access failed:', err);
            updateUIForError('Microphone access denied');
        }
    }

    function stopMicrophone() {
        isRecording = false;
        saveMicrophoneState(false); // save state
        smoothedDb = 0; // Reset smoothing
        lastUpdateTime = 0; // Reset throttle

        if (animationId) {
            cancelAnimationFrame(animationId);
            animationId = null;
        }
        if (sendIntervalId) {
            clearInterval(sendIntervalId);
            sendIntervalId = null;
        }
        if (mediaStream) {
            mediaStream.getTracks().forEach(track => track.stop());
            mediaStream = null;
        }
        if (audioContext) {
            audioContext.close();
            audioContext = null;
        }

        updateUIForStopped();
    }

    // update UI for recording state
    function updateUIForRecording() {
        const startBtn = document.getElementById('start-mic');
        const stopBtn = document.getElementById('stop-mic');
        const micStatus = document.getElementById('mic-status');
        
        if (startBtn) startBtn.disabled = true;
        if (stopBtn) stopBtn.disabled = false;
        if (micStatus) {
            micStatus.textContent = 'Microphone active - recording...';
            micStatus.style.color = '#28a745';
        }
    }

    function updateUIForStopped() {
        const startBtn = document.getElementById('start-mic');
        const stopBtn = document.getElementById('stop-mic');
        const micStatus = document.getElementById('mic-status');
        const dbDisplay = document.getElementById('realtime-db');
        
        if (startBtn) startBtn.disabled = false;
        if (stopBtn) stopBtn.disabled = true;
        if (micStatus) {
            micStatus.textContent = 'Microphone inactive';
            micStatus.style.color = '#666';
        }
        if (dbDisplay) {
            dbDisplay.textContent = '-- dB';
            dbDisplay.style.color = '#333';
        }
    }

    function updateUIForError(message) {
        const micStatus = document.getElementById('mic-status');
        if (micStatus) {
            micStatus.textContent = message;
            micStatus.style.color = '#dc3545';
        }
    }

    // auto resume recording if previously active
    async function autoResumeRecording() {
        const shouldResume = loadMicrophoneState();
        if (shouldResume) {
            console.log('Auto-resuming microphone recording...');
            await startMicrophone();
        }
    }

    // Purge data handler
    async function purgeData() {
        if (!confirm('Are you sure you want to delete all measurement data? This cannot be undone.')) {
            return;
        }
        
        const btn = document.getElementById('purge-btn');
        const status = document.getElementById('purge-status');
        
        btn.disabled = true;
        status.textContent = 'Purging data...';
        status.style.color = '#666';
        
        try {
            const resp = await fetch('/api/purge', { method: 'POST' });
            const data = await resp.json();
            
            if (data.ok) {
                status.textContent = data.message;
                status.style.color = '#28a745';
            } else {
                status.textContent = 'Error: ' + data.error;
                status.style.color = '#dc3545';
            }
        } catch (err) {
            status.textContent = 'Failed to purge data: ' + err.message;
            status.style.color = '#dc3545';
        } finally {
            btn.disabled = false;
            setTimeout(() => {
                status.textContent = '';
            }, 5000);
        }
    }

    // Initialize on page load
    document.addEventListener('DOMContentLoaded', async () => {
        const startBtn = document.getElementById('start-mic');
        const stopBtn = document.getElementById('stop-mic');
        const purgeBtn = document.getElementById('purge-btn');
        
        // Fetch interval configuration once on page load
        try {
            const configResp = await fetch('/api/config');
            const config = await configResp.json();
            intervalMs = config.interval_ms || 5000; // Update module-level variable
        } catch (err) {
            console.error('Failed to fetch config, using default interval:', err);
        }
        
        // Set up event listeners
        if (startBtn) startBtn.addEventListener('click', startMicrophone);
        if (stopBtn) stopBtn.addEventListener('click', stopMicrophone);
        if (purgeBtn) purgeBtn.addEventListener('click', purgeData);

        // Auto-resume if previously recording
        await autoResumeRecording();
    });

    // Save state on page unload
    window.addEventListener('beforeunload', () => {
        if (isRecording) {
            saveMicrophoneState(true);
        }
    });
})();
