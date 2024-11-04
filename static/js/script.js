async function processVideo() {
    const url = document.getElementById('tiktokUrl').value;
    const lang = document.getElementById('language').value;

    if (!url) {
        showAlert('Please enter TikTok URL', 'danger');
        return;
    }

    // Show progress container and reset alerts
    const progressContainer = document.getElementById('progress-container');
    progressContainer.style.display = 'block';
    hideAlert();

    // Progress bar elements
    const downloadProgress = document.getElementById('download-progress');
    const processProgress = document.getElementById('process-progress');

    // Initialize progress bars
    updateProgress(downloadProgress, 0);
    updateProgress(processProgress, 0);

    // Clear previous results
    updateContent('transcription', 'Processing...');
    updateContent('summary', 'Processing...');

    try {
        let combinedPercent = 0;

        // --- Download simulation ---
        const downloadInterval = setInterval(() => {
            if (combinedPercent < 50) {
                combinedPercent += 1;
                updateProgress(downloadProgress, combinedPercent);
            }
        }, 50);

        const response = await fetch('/process', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ url: url, target_language: lang })
        });

        clearInterval(downloadInterval);
        updateProgress(downloadProgress, 100);

        // --- Processing simulation ---
        let processPercent = 0;
        const processInterval = setInterval(() => {
            if (processPercent < 100) {
                processPercent += 1;
                updateProgress(processProgress, processPercent);
            } else {
                clearInterval(processInterval);
            }
        }, 50);

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Network response was not ok');
        }

        const data = await response.json();

        // Update results
        updateContent('transcription', data.transcription);
        updateContent('summary', data.summary);

    } catch (error) {
        console.error('Error details:', error);
        showAlert(`Error processing video: ${error.message}`, 'danger');
        updateContent('transcription', 'Error occurred: ' + error.message);
        updateContent('summary', 'Processing failed. Please try again.');
    } finally {
        // Hide progress after a delay
        setTimeout(() => {
            progressContainer.style.display = 'none';
            updateProgress(downloadProgress, 0);
            updateProgress(processProgress, 0);
        }, 2000);
    }
}

async function extractAudio() {
    const url = document.getElementById('tiktokUrl').value;
    const audioStatus = document.getElementById('audio-status');
    const extractBtn = document.getElementById('extract-audio-btn');
    const processingIndicator = extractBtn.querySelector('.processing-indicator');

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

        // Create download button
        const downloadBtn = document.createElement('a');
        downloadBtn.href = `/download-audio/${data.audio_path}`;
        downloadBtn.className = 'btn btn-success download-link';
        downloadBtn.innerText = 'Download Audio';
        downloadBtn.download = data.audio_path;

        // Update status
        audioStatus.innerText = '';
        audioStatus.appendChild(downloadBtn);

    } catch (error) {
        console.error('Error:', error);
        showAlert('Failed to extract audio. Please try again.', 'danger');
        audioStatus.innerText = '';
    } finally {
        extractBtn.disabled = false;
        processingIndicator.style.display = 'none';
    }
}

function updateProgress(progressBar, percent) {
    if (progressBar) {
        progressBar.style.width = `${percent}%`;
        progressBar.innerText = `${percent}%`;
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
                btn.innerText = 'Copied!';
                setTimeout(() => {
                    btn.innerText = originalText;
                }, 2000);
            }
        })
        .catch(err => {
            console.error('Failed to copy:', err);
            showAlert("Could not copy text. Please try manually selecting and copying.", 'danger');
        });
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

// Optional: Add event listeners for keyboard shortcuts
document.addEventListener('DOMContentLoaded', () => {
    // Process video on Enter key in URL input
    document.getElementById('tiktokUrl').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            processVideo();
        }
    });

    // Handle paste events to clean URLs
    document.getElementById('tiktokUrl').addEventListener('paste', (e) => {
        e.preventDefault();
        const text = e.clipboardData.getData('text');
        const cleanUrl = text.trim(); // You can add more URL cleaning logic here
        e.target.value = cleanUrl;
    });
});
