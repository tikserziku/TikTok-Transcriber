// Utility functions
function updateProgress(progressBar, percent) {
    if (progressBar) {
        progressBar.style.width = `${percent}%`;
        progressBar.innerText = `${percent}%`;
        progressBar.setAttribute('aria-valuenow', percent);
    }
}

function updateContent(elementId, content) {
    const element = document.getElementById(elementId);
    if (element) {
        const contentElement = element.querySelector('.content');
        if (contentElement) {
            contentElement.innerText = content;
        }
    }
}

function showAlert(message, type = 'danger') {
    const alertBox = document.querySelector('.alert');
    if (alertBox) {
        alertBox.innerText = message;
        alertBox.className = `alert alert-${type}`;
        alertBox.style.display = 'block';
    }
}

function hideAlert() {
    const alertBox = document.querySelector('.alert');
    if (alertBox) {
        alertBox.style.display = 'none';
    }
}

// Main functions
async function extractAudio() {
    const url = document.getElementById('tiktokUrl').value;
    const audioStatus = document.getElementById('audio-status');
    const extractBtn = document.getElementById('extract-audio-btn');
    const processingIndicator = extractBtn.querySelector('.processing-indicator');
    const processingOptions = document.getElementById('processing-options');

    if (!url) {
        showAlert('Please enter TikTok URL', 'danger');
        return;
    }

    try {
        // Update UI for processing state
        extractBtn.disabled = true;
        processingIndicator.style.display = 'inline-block';
        audioStatus.innerText = 'Extracting audio...';
        hideAlert();

        const response = await fetch('/extract-audio', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                url: url,
                target_language: document.getElementById('language').value
            })
        });

        if (!response.ok) {
            throw new Error('Failed to extract audio');
        }

        const data = await response.json();

        // Clear previous content and hide error
        audioStatus.innerText = '';
        hideAlert();
        
        // Add file info
        if (data.size_mb) {
            const fileInfo = document.createElement('div');
            fileInfo.className = 'text-muted mb-2';
            fileInfo.innerText = `File size: ${data.size_mb.toFixed(2)} MB`;
            audioStatus.appendChild(fileInfo);
        }

        // Add download button
        const downloadBtn = document.createElement('a');
        downloadBtn.href = `/download-audio/${data.audio_path}`;
        downloadBtn.className = 'btn btn-success mb-3 w-100';
        downloadBtn.innerText = 'Download Audio';
        downloadBtn.download = data.audio_path;
        audioStatus.appendChild(downloadBtn);

        // Show processing options
        processingOptions.style.display = 'block';

    } catch (error) {
        console.error('Error:', error);
        showAlert('Failed to extract audio. Please try again.', 'danger');
        audioStatus.innerText = '';
    } finally {
        extractBtn.disabled = false;
        processingIndicator.style.display = 'none';
    }
}

async function processAudio() {
    const url = document.getElementById('tiktokUrl').value;
    const lang = document.getElementById('language').value;
    const resultsSection = document.getElementById('results-section');
    
    // Hide processing options while processing
    const processingOptions = document.getElementById('processing-options');
    processingOptions.style.display = 'none';
    
    // Show progress
    const progressContainer = document.getElementById('progress-container');
    progressContainer.style.display = 'block';
    
    const processProgress = document.getElementById('process-progress');
    updateProgress(processProgress, 0);

    try {
        hideAlert();
        updateContent('transcription', 'Processing...');
        updateContent('summary', 'Processing...');

        // Show results section
        resultsSection.style.display = 'flex';

        // Start progress simulation
        let processPercent = 0;
        const processInterval = setInterval(() => {
            if (processPercent < 90) {  // Only go up to 90% in simulation
                processPercent += 1;
                updateProgress(processProgress, processPercent);
            }
        }, 100);

        const response = await fetch('/process', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ url: url, target_language: lang })
        });

        if (!response.ok) {
            throw new Error('Failed to process audio');
        }

        const data = await response.json();

        // Complete progress bar
        clearInterval(processInterval);
        updateProgress(processProgress, 100);

        // Update results
        updateContent('transcription', data.transcription || 'Transcription failed');
        updateContent('summary', data.summary || 'Summary not available');

    } catch (error) {
        console.error('Error:', error);
        showAlert('Failed to process audio. Please try NotebookLM instead.', 'danger');
        resultsSection.style.display = 'none';
        processingOptions.style.display = 'block'; // Show options again on error
    } finally {
        setTimeout(() => {
            progressContainer.style.display = 'none';
            updateProgress(processProgress, 0);
        }, 2000);
    }
}

function copyText(elementId) {
    const element = document.getElementById(elementId);
    if (!element) {
        showAlert(`Element "${elementId}" not found.`, 'danger');
        return;
    }

    const contentElement = element.querySelector('.content');
    if (!contentElement) {
        showAlert(`Content element within "${elementId}" not found.`, 'danger');
        return;
    }

    const textToCopy = contentElement.innerText;

    navigator.clipboard.writeText(textToCopy)
        .then(() => {
            const btn = element.querySelector('.copy-btn');
            if (btn) {
                const originalText = btn.innerText;
                btn.innerHTML = `
                    Copied! 
                    <span class="small d-block">
                        Open NotebookLM to paste
                    </span>
                `;
                
                const nlmBtn = document.createElement('a');
                nlmBtn.href = 'https://notebooklm.google.com/';
                nlmBtn.target = '_blank';
                nlmBtn.rel = 'noopener noreferrer';
                nlmBtn.className = 'btn btn-sm btn-primary mt-2';
                nlmBtn.innerHTML = 'Open NotebookLM';
                
                btn.parentElement.appendChild(nlmBtn);
                
                setTimeout(() => {
                    btn.innerText = originalText;
                    if (nlmBtn.parentElement) {
                        nlmBtn.parentElement.removeChild(nlmBtn);
                    }
                }, 3000);
            }
        })
        .catch(err => {
            console.error('Failed to copy:', err);
            showAlert("Could not copy text. Please try manually selecting and copying.", 'danger');
        });
}

// Event Listeners
document.addEventListener('DOMContentLoaded', () => {
    // Clean URLs on paste
    document.getElementById('tiktokUrl').addEventListener('paste', (e) => {
        e.preventDefault();
        const text = e.clipboardData.getData('text');
        const cleanUrl = text.trim();
        e.target.value = cleanUrl;
    });
});
