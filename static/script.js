// Global variables
let currentThreadId = null;
let progressInterval = null;

// DOM elements
const urlInput = document.getElementById('urlInput');
const captureBtn = document.getElementById('captureBtn');
const btnText = document.querySelector('.btn-text');
const btnLoader = document.querySelector('.btn-loader');
const progressContainer = document.getElementById('progressContainer');
const progressText = document.getElementById('progressText');
const progressFill = document.querySelector('.progress-fill');
const capturesList = document.getElementById('capturesList');
const welcomeScreen = document.getElementById('welcomeScreen');
const comparisonView = document.getElementById('comparisonView');

// Initialize app
document.addEventListener('DOMContentLoaded', function() {
    // Set up event listeners
    captureBtn.addEventListener('click', startCapture);
    urlInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            startCapture();
        }
    });
    
    // Focus on URL input
    urlInput.focus();
    
    // Set up comparison view controls
    setupComparisonControls();
    
    // Load initial captures
    loadCaptures();
});

// Start website capture
async function startCapture() {
    const url = urlInput.value.trim();
    
    if (!url) {
        alert('Please enter a valid URL');
        return;
    }
    
    // Validate URL
    if (!isValidUrl(url)) {
        alert('Please enter a valid URL (e.g., https://example.com)');
        return;
    }
    
    // Update UI to show loading state
    setLoadingState(true);
    showProgress();
    
    try {
        // Start capture
        const response = await fetch('/api/capture', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ url: url })
        });
        
        const data = await response.json();
        
        if (data.error) {
            throw new Error(data.error);
        }
        
        currentThreadId = data.thread_id;
        
        // Start polling for progress
        startProgressPolling();
        
    } catch (error) {
        console.error('Error starting capture:', error);
        alert('Error starting capture: ' + error.message);
        setLoadingState(false);
        hideProgress();
    }
}

// Validate URL format
function isValidUrl(string) {
    try {
        const url = new URL(string);
        return url.protocol === 'http:' || url.protocol === 'https:';
    } catch (_) {
        return false;
    }
}

// Set loading state
function setLoadingState(loading) {
    if (loading) {
        captureBtn.disabled = true;
        btnText.classList.add('hidden');
        btnLoader.classList.remove('hidden');
        urlInput.disabled = true;
    } else {
        captureBtn.disabled = false;
        btnText.classList.remove('hidden');
        btnLoader.classList.add('hidden');
        urlInput.disabled = false;
    }
}

// Show progress container
function showProgress() {
    progressContainer.classList.remove('hidden');
    progressText.textContent = 'Starting capture...';
    progressFill.style.width = '10%';
}

// Hide progress container
function hideProgress() {
    progressContainer.classList.add('hidden');
    progressFill.style.width = '0%';
}

// Start polling for progress updates
function startProgressPolling() {
    if (progressInterval) {
        clearInterval(progressInterval);
    }
    
    progressInterval = setInterval(async () => {
        if (!currentThreadId) return;
        
        try {
            const response = await fetch(`/api/progress/${currentThreadId}`);
            const progress = await response.json();
            
            updateProgress(progress);
            
            if (progress.status === 'completed' || progress.status === 'error') {
                stopProgressPolling();
                setLoadingState(false);
                
                if (progress.status === 'completed') {
                    hideProgress();
                    showSuccess();
                    loadCaptures(); // Refresh captures list
                } else {
                    hideProgress();
                    alert('Capture failed: ' + progress.message);
                }
            }
            
        } catch (error) {
            console.error('Error polling progress:', error);
            stopProgressPolling();
            setLoadingState(false);
            hideProgress();
            alert('Error checking progress: ' + error.message);
        }
    }, 1000); // Poll every second
}

// Stop progress polling
function stopProgressPolling() {
    if (progressInterval) {
        clearInterval(progressInterval);
        progressInterval = null;
    }
    currentThreadId = null;
}

// Update progress display
function updateProgress(progress) {
    if (progress.message) {
        progressText.textContent = progress.message;
    }
    
    // Update progress bar based on status
    let percentage = 10;
    if (progress.message) {
        if (progress.message.includes('Loading')) percentage = 20;
        else if (progress.message.includes('Extracting')) percentage = 30;
        else if (progress.message.includes('Discovering')) percentage = 40;
        else if (progress.message.includes('Downloading')) percentage = 70;
        else if (progress.message.includes('Rewriting')) percentage = 90;
        else if (progress.message.includes('completed')) percentage = 100;
    }
    
    progressFill.style.width = percentage + '%';
}

// Show success message
function showSuccess() {
    progressText.textContent = '✅ Capture completed successfully!';
    progressFill.style.width = '100%';
    
    setTimeout(() => {
        hideProgress();
    }, 2000);
}

// Load captures from server
async function loadCaptures() {
    try {
        const response = await fetch('/api/captures');
        const captures = await response.json();
        
        updateCapturesList(captures);
        
    } catch (error) {
        console.error('Error loading captures:', error);
    }
}

// Update captures list in UI
function updateCapturesList(captures) {
    if (captures.length === 0) {
        capturesList.innerHTML = `
            <div class="empty-state">
                <p>No captures yet. Enter a URL above to get started!</p>
            </div>
        `;
        return;
    }
    
    capturesList.innerHTML = captures.map(capture => `
        <div class="capture-item" data-folder="${capture.folder_name}">
            <div class="capture-info">
                <div class="capture-url">${capture.original_url}</div>
                <div class="capture-time">${formatDateTime(capture.capture_time)}</div>
                <div class="capture-stats">
                    CSS: ${capture.assets.css} | 
                    JS: ${capture.assets.js} | 
                    Images: ${capture.assets.images}
                </div>
            </div>
            <div class="capture-actions">
                <button class="btn-view" onclick="viewCapture('${capture.folder_name}')">View</button>
                <button class="btn-compare" onclick="compareCapture('${capture.folder_name}')">Compare</button>
                <button class="btn-download" onclick="downloadCapture('${capture.folder_name}')">⬇️</button>
                <button class="btn-delete" onclick="deleteCapture('${capture.folder_name}')">🗑️</button>
            </div>
        </div>
    `).join('');
}

// Format date time for display
function formatDateTime(isoString) {
    const date = new Date(isoString);
    return date.toLocaleString();
}

// View capture in full screen
function viewCapture(folderName) {
    window.open(`/view/${folderName}`, '_blank');
}

// Compare capture with original
function compareCapture(folderName) {
    // Show comparison view in main area
    welcomeScreen.classList.add('hidden');
    comparisonView.classList.remove('hidden');
    
    // Load comparison data
    loadComparison(folderName);
}

// Load comparison data
async function loadComparison(folderName) {
    try {
        // Get capture metadata
        const response = await fetch('/api/captures');
        const captures = await response.json();
        const capture = captures.find(c => c.folder_name === folderName);
        
        if (!capture) {
            alert('Capture not found');
            return;
        }
        
        // Update comparison view
        document.getElementById('comparisonTitle').textContent = `Comparing: ${capture.original_url}`;
        
        // Load iframes
        const originalIframe = document.getElementById('originalIframe');
        const capturedIframe = document.getElementById('capturedIframe');
        
        originalIframe.src = capture.original_url;
        capturedIframe.src = `/captured/${folderName}/index.html`;
        
    } catch (error) {
        console.error('Error loading comparison:', error);
        alert('Error loading comparison: ' + error.message);
    }
}

// Set up comparison view controls
function setupComparisonControls() {
    const splitViewBtn = document.getElementById('splitViewBtn');
    const originalViewBtn = document.getElementById('originalViewBtn');
    const capturedViewBtn = document.getElementById('capturedViewBtn');
    const newTabBtn = document.getElementById('newTabBtn');
    
    if (!splitViewBtn) return; // Elements might not exist yet
    
    splitViewBtn.addEventListener('click', () => {
        setComparisonMode('split');
        setActiveButton(splitViewBtn);
    });
    
    originalViewBtn.addEventListener('click', () => {
        setComparisonMode('original');
        setActiveButton(originalViewBtn);
    });
    
    capturedViewBtn.addEventListener('click', () => {
        setComparisonMode('captured');
        setActiveButton(capturedViewBtn);
    });
    
    newTabBtn.addEventListener('click', () => {
        const capturedIframe = document.getElementById('capturedIframe');
        if (capturedIframe.src) {
            window.open(capturedIframe.src, '_blank');
        }
    });
}

// Set comparison mode
function setComparisonMode(mode) {
    const originalFrame = document.getElementById('originalFrame');
    const capturedFrame = document.getElementById('capturedFrame');
    
    if (mode === 'split') {
        originalFrame.style.display = 'block';
        capturedFrame.style.display = 'block';
        originalFrame.style.width = '50%';
        capturedFrame.style.width = '50%';
    } else if (mode === 'original') {
        originalFrame.style.display = 'block';
        capturedFrame.style.display = 'none';
        originalFrame.style.width = '100%';
    } else if (mode === 'captured') {
        originalFrame.style.display = 'none';
        capturedFrame.style.display = 'block';
        capturedFrame.style.width = '100%';
    }
}

// Set active button
function setActiveButton(activeBtn) {
    const buttons = document.querySelectorAll('.control-btn');
    buttons.forEach(btn => btn.classList.remove('active'));
    activeBtn.classList.add('active');
}

// Download capture as ZIP
function downloadCapture(folderName) {
    window.location.href = `/download/${folderName}`;
}

// Delete capture
async function deleteCapture(folderName) {
    if (!confirm('Are you sure you want to delete this capture?')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/delete/${folderName}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (data.error) {
            throw new Error(data.error);
        }
        
        // Refresh captures list
        loadCaptures();
        
        // Hide comparison view if this capture was being viewed
        comparisonView.classList.add('hidden');
        welcomeScreen.classList.remove('hidden');
        
    } catch (error) {
        console.error('Error deleting capture:', error);
        alert('Error deleting capture: ' + error.message);
    }
}

// Back to home
function backToHome() {
    comparisonView.classList.add('hidden');
    welcomeScreen.classList.remove('hidden');
}

// Keyboard shortcuts
document.addEventListener('keydown', function(e) {
    // Ctrl/Cmd + Enter to capture
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        if (!captureBtn.disabled) {
            startCapture();
        }
    }
    
    // Escape to go back to home
    if (e.key === 'Escape') {
        backToHome();
    }
});

// Auto-focus URL input when clicking anywhere on welcome screen
document.addEventListener('click', function(e) {
    if (e.target.closest('.welcome-screen')) {
        urlInput.focus();
    }
});

// Handle window beforeunload
window.addEventListener('beforeunload', function() {
    if (progressInterval) {
        clearInterval(progressInterval);
    }
});