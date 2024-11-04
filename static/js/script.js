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
        // --- Download simulation ---
        const downloadInterval = setInterval(() => {
            const percent = parseInt(downloadProgress.style.width) || 0;
            if (percent < 100) {
                updateProgress(downloadProgress, Math.min(percent + 2, 100));
            }
        }, 100);

        const response = await fetch('/process', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ url: url, target_language: lang })
        });

        clearInterval(downloadInterval);
        updateProgress(downloadProgress, 100);

        if (!response.ok) {
            const errorData = await response.json();
            
            // Check if it's a video length error
            if (errorData.detail && errorData.detail.includes("too long")) {
                const errorMessage = `
                    This video is too long for automatic transcription. 
                    You can:
                    1. Download the audio file and use NotebookLM (https://notebooklm.google.com/)
                    2. Try using the "Extract Audio" button below
                    3. Split the video into smaller parts
                `;
                updateContent('transcription', errorMessage);
                updateContent('summary', 'Processing not available for long videos');
                showAudioExtractionOption();
                return;
            }
            
            throw new Error(errorData.detail || 'Network response was not ok');
        }

        const data = await response.json();

        // Show processing progress
        const processInterval = setInterval(() => {
            const percent = parseInt(processProgress.style.width) || 0;
            if (percent < 100) {
                updateProgress(processProgress, Math.min(percent + 2, 100));
            } else {
                clearInterval(processInterval);
            }
        }, 100);

        // Update results
        updateContent('transcription', data.transcription || 'Transcription failed');
        updateContent('summary', data.summary || 'Summary not available');

        // If audio is available, show download option
        if (data.audio_path) {
            showAudioDownloadOption(data.audio_path);
        }

        clearInterval(processInterval);
        updateProgress(processProgress, 100);

    } catch (error) {
        console.error('Error details:', error);
        const errorMessage = error.message.includes("too long") 
            ? `This video is too long for automatic transcription.\nPlease use the "Extract Audio" button to get the audio file and process it manually.`
            : `Error processing video: ${error.message}`;
        
        showAlert(errorMessage, 'danger');
        updateContent('transcription', errorMessage);
        updateContent('summary', 'Processing failed. Please try again.');
    } finally {
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

        // Clear previous content
        audioStatus.innerText = '';
        
        // Add file info if available
        if (data.size_mb) {
            const fileInfo = document.createElement('div');
            fileInfo.className = 'text-muted mb-2';
            fileInfo.innerText = `File size: ${data.size_mb.toFixed(2)} MB`;
            audioStatus.appendChild(fileInfo);
        }

        // Add download button
        audioStatus.appendChild(downloadBtn);

        // Add usage instructions
        const instructions = document.createElement('div');
        instructions.className = 'alert alert-info mt-3';
        instructions.innerHTML = `
            <strong>Next steps:</strong>
            <ul class="mb-0">
                <li>Download the audio file</li>
                <li>Visit <a href="https://notebooklm.google.com/" target="_blank">NotebookLM</a></li>
                <li>Upload the audio file for transcription</li>
            </ul>
        `;
        audioStatus.appendChild(instructions);

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

function showAudioExtractionOption() {
    const audioSection = document.getElementById('audio-download');
    if (audioSection) {
        audioSection.style.display = 'block';
        const notice = document.createElement('div');
        notice.className = 'alert alert-info mt-3';
        notice.innerHTML = `
            You can use the extracted audio file with:
            <ul>
                <li><a href="https://notebooklm.google.com/" target="_blank">NotebookLM</a></li>
                <li>Other transcription services</li>
                <li>Local speech-to-text tools</li>
            </ul>
        `;
        audioSection.appendChild(notice);
    }
}

function showAudioDownloadOption(audioPath) {
    const audioSection = document.getElementById('audio-download');
    if (audioSection) {
        const downloadLink = document.createElement('a');
        downloadLink.href = `/download-audio/${audioPath}`;
        downloadLink.className = 'btn btn-success mt-2';
        downloadLink.innerText = 'Download Audio File';
        downloadLink.download = audioPath;
        audioSection.appendChild(downloadLink);
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

// Event listeners
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
        const cleanUrl = text.trim();
        e.target.value = cleanUrl;
    });
});
