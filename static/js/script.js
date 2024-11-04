async function processVideo() {
    const url = document.getElementById('tiktokUrl').value;
    const lang = document.getElementById('language').value;

    if (!url) {
        alert('Please enter TikTok URL');
        return;
    }

    // Show progress
    const progressContainer = document.getElementById('progress-container');
    progressContainer.style.display = 'block';
    const downloadProgress = document.getElementById('download-progress');
    const processProgress = document.getElementById('process-progress');
    updateProgress(downloadProgress, 0);
    updateProgress(processProgress, 0);

    // Clear previous results
    document.getElementById('transcription').querySelector('.content').innerText = 'Processing...';
    document.getElementById('summary').querySelector('.content').innerText = 'Processing...';
    const downloadLinkContainer = document.getElementById('download-link'); // Get download link container
    downloadLinkContainer.innerHTML = ''; // Clear previous download link

    try {
        let downloadPercent = 0;
        let processPercent = 0;

        const downloadInterval = setInterval(() => {
            if (downloadPercent < 50) {
                downloadPercent += 1;
                updateProgress(downloadProgress, downloadPercent);
            }
        }, 50);

        const response = await fetch('/process', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: url, target_language: lang }),
            timeout: 120000
        });

        clearInterval(downloadInterval);
        updateProgress(downloadProgress, 100);

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

        document.getElementById('transcription').querySelector('.content').innerText = data.transcription;
        document.getElementById('summary').querySelector('.content').innerText = data.summary;


         // Add download link if audio_url is present
        if (data.audio_url) {
            const downloadLink = document.createElement('a');
            downloadLink.href = data.audio_url;
            downloadLink.className = 'btn btn-success'; // Add Bootstrap button class
            downloadLink.download = 'audio.mp3'; // Suggest filename for download.  You might want to make this dynamic based on the video title.
            downloadLink.innerText = 'Download MP3';
            downloadLinkContainer.appendChild(downloadLink);

        }


    } catch (error) {
        console.error('Error details:', error);
        alert(`Error processing video: ${error.message}`);
        document.getElementById('transcription').querySelector('.content').innerText = 'Error occurred: ' + error.message;
        document.getElementById('summary').querySelector('.content').innerText = 'Processing failed. Please try again.';
    } finally {
        setTimeout(() => {
            progressContainer.style.display = 'none';
            updateProgress(downloadProgress, 0);
            updateProgress(processProgress, 0);
        }, 2000);
    }
}

function updateProgress(progressBar, percent) {
    if (progressBar) {
        progressBar.style.width = `${percent}%`;
        progressBar.innerText = `${percent}%`;
    }
}
function copyText(elementId) {
    const element = document.getElementById(elementId); // Get the parent element (transcription or summary)

    if (!element) {
        console.error(`Element with id "${elementId}" not found.`);
        return; // Or show an error message to the user.
    }

    const contentElement = element.querySelector('.content');

     if (!contentElement) {
        console.error(`Content element within "${elementId}" not found.`);
        return;
    }

    const textToCopy = contentElement.innerText;

    navigator.clipboard.writeText(textToCopy)
        .then(() => {
            // Show a temporary "Copied!" message
            const btn = element.querySelector('.copy-btn');
            if (btn) {
                const originalText = btn.innerText;
                btn.innerText = 'Copied!';
                setTimeout(() => {
                    btn.innerText = originalText;
                }, 2000); // Change back after 2 seconds
            }


        })
        .catch(err => {
            console.error('Failed to copy: ', err);
            // Optionally show an error message to the user
            alert("Could not copy text. Please try manually selecting and copying.");

        });
}
