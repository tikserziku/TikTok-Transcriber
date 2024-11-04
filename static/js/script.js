async function processVideo() {
    const url = document.getElementById('tiktokUrl').value;
    const lang = document.getElementById('language').value;

    if (!url) {
        showAlert('Please enter TikTok URL', 'danger');
        return;
    }

    const progressContainer = document.getElementById('progress-container');
    progressContainer.style.display = 'block';
    hideAlert();

    const downloadProgress = document.getElementById('download-progress');
    const processProgress = document.getElementById('process-progress');

    updateProgress(downloadProgress, 0);
    updateProgress(processProgress, 0);

    updateContent('transcription', 'Processing...');
    updateContent('summary', 'Processing...');

    try {
        // Download - 30%
        let downloadPercent = 0;
        const downloadInterval = setInterval(() => {
            if (downloadPercent < 30) {
                downloadPercent += 1;
                updateProgress(downloadProgress, downloadPercent);
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

        // Processing progress simulation based on typical timings
        let processPercent = 0;
        const processInterval = setInterval(() => {
            // Audio extraction: 0-30%
            if (processPercent < 30) {
                processPercent += 2;
            } 
            // Transcription: 30-70%
            else if (processPercent < 70) {
                processPercent += 1;
            }
            // Summary generation: 70-100%
            else if (processPercent < 100) {
                processPercent += 0.5;
            }
            
            updateProgress(processProgress, Math.min(processPercent, 100));
            
            if (processPercent >= 100) {
                clearInterval(processInterval);
            }
        }, 200);

        const data = await response.json();

        // Clear any remaining intervals
        clearInterval(processInterval);
        updateProgress(processProgress, 100);

        // Update results
        updateContent('transcription', data.transcription || 'Transcription failed');
        updateContent('summary', data.summary || 'Summary not available');

        // Show audio download if available
        if (data.audio_path) {
            showAudioDownloadOption(data.audio_path);
        }

    } catch (error) {
        console.error('Error details:', error);
        const errorMessage = error.message.includes("too long") 
            ? `This video is too long for automatic transcription.\nPlease use the "Extract Audio" button to get the audio file and process it manually.`
            : `Error processing video: ${error.message}`;
        
        showAlert(errorMessage, 'danger');
        updateContent('transcription', errorMessage);
        updateContent('summary', 'Processing failed. Please try again.');
    } finally {
        // Hide progress after delay
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

        audioStatus.innerText = '';
        
        if (data.size_mb) {
            const fileInfo = document.createElement('div');
            fileInfo.className = 'text-muted mb-2';
            fileInfo.innerText = `File size: ${data.size_mb.toFixed(2)} MB`;
            audioStatus.appendChild(fileInfo);
        }

        const downloadBtn = document.createElement('a');
        downloadBtn.href = `/download-audio/${data.audio_path}`;
        downloadBtn.className = 'btn btn-success download-link';
        downloadBtn.innerText = 'Download Audio';
        downloadBtn.download = data.audio_path;
        audioStatus.appendChild(downloadBtn);

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
        progressBar.setAttribute('aria-valuenow', percent);
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

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('tiktokUrl').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            processVideo();
        }
    });

    document.getElementById('tiktokUrl').addEventListener('paste', (e) => {
        e.preventDefault();
        const text = e.clipboardData.getData('text');
        const cleanUrl = text.trim();
        e.target.value = cleanUrl;
    });
});
