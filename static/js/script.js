async function processVideo() {
    const url = document.getElementById('tiktokUrl').value;
    const lang = document.getElementById('language').value;

    if (!url) {
        alert('Please enter TikTok URL');
        return;
    }


    // Progress elements and container
    const progressContainer = document.getElementById('progress-container');
    const downloadProgress = document.getElementById('download-progress');
    const processProgress = document.getElementById('process-progress');

    progressContainer.style.display = 'block'; // Show progress container
    updateProgress(downloadProgress, 0);
    updateProgress(processProgress, 0);



    // Clear previous results
    document.getElementById('transcription').querySelector('.content').innerText = 'Processing...';
    document.getElementById('summary').querySelector('.content').innerText = 'Processing...';


    try {
        let downloadPercent = 0;
        let processPercent = 0;


        const downloadInterval = setInterval(() => {
            if (downloadPercent < 50) {  // Simulate download to 50%
                downloadPercent += 1;
                updateProgress(downloadProgress, downloadPercent);
            }
        }, 50);



        const response = await fetch('/process', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ url: url, target_language: lang }),
            timeout: 120000
        });



        clearInterval(downloadInterval); // Stop download simulation
        updateProgress(downloadProgress, 100);


        const processInterval = setInterval(() => {
            if (processPercent < 100) {   // Simulate processing to 100%
                processPercent += 1;
                updateProgress(processProgress, processPercent);
            }
            else {
                clearInterval(processInterval);
            }
        }, 50);



        if (!response.ok) {
            const errorData = await response.json(); // Get error details from response
            throw new Error(errorData.detail || 'Network response was not ok');
        }

        const data = await response.json();


        document.getElementById('transcription').querySelector('.content').innerText = data.transcription;
        document.getElementById('summary').querySelector('.content').innerText = data.summary;


    } catch (error) {
        console.error('Error details:', error);
        alert(`Error processing video: ${error.message}`);
        document.getElementById('transcription').querySelector('.content').innerText = 'Error occurred: ' + error.message;
        document.getElementById('summary').querySelector('.content').innerText = 'Processing failed. Please try again.';

    } finally {
        // Hide progress after a delay
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

// Copy text function (unchanged)
// ...
