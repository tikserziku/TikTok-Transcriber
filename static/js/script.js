async function processVideo() {
    const url = document.getElementById('tiktokUrl').value;
    const lang = document.getElementById('language').value;

    if (!url) {
        alert('Please enter TikTok URL');
        return;
    }

    // Показываем прогресс
    const progressContainer = document.getElementById('progress-container');
    const downloadProgress = document.getElementById('download-progress'); // Correct ID
    const processProgress = document.getElementById('process-progress'); // Correct ID
    progressContainer.style.display = 'block';  // Make progress container visible

    // Initialize BOTH progress bars
    updateProgress(downloadProgress, 0); 
    updateProgress(processProgress, 0);


    // Очищаем предыдущие результаты
    document.getElementById('transcription').querySelector('.content').innerText = 'Processing...';
    document.getElementById('summary').querySelector('.content').innerText = 'Processing...';

    try {
        let downloadPercent = 0;
        let processPercent = 0;

        // Simulate download progress (replace with actual progress if available)
        const downloadInterval = setInterval(() => {
            if (downloadPercent < 95) {
                downloadPercent += 1;
                updateProgress(downloadProgress, downloadPercent);
            }
        }, 50);

        const response = await fetch('/process', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                url: url,
                target_language: lang
            }),
            timeout: 120000  // 2 минуты таймаут
        });

        clearInterval(downloadInterval);  // Stop download simulation
        updateProgress(downloadProgress, 100);  // Download complete (100%)

        // Simulate processing progress (replace with actual progress if available)
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


    } catch (error) {
        console.error('Error details:', error);
        alert(`Error processing video: ${error.message}`);
        document.getElementById('transcription').querySelector('.content').innerText = 'Error occurred: ' + error.message;
        document.getElementById('summary').querySelector('.content').innerText = 'Processing failed. Please try again.';
    } finally {
        // Скрываем прогресс через 2 секунды
        setTimeout(() => {
            progressContainer.style.display = 'none';
            updateProgress(downloadProgress, 0); // Reset download progress
            updateProgress(processProgress, 0); // Reset process progress
        }, 2000);
    }
}



function updateProgress(progressBar, percent) { // Takes the progress bar element and percent

    if (progressBar) {
        progressBar.style.width = `${percent}%`;
        progressBar.innerText = `${percent}%`;
    }
}
