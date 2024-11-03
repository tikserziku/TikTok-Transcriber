async function processVideo() {
    const url = document.getElementById('tiktokUrl').value;
    const lang = document.getElementById('language').value;

    if (!url) {
        alert('Please enter TikTok URL');
        return;
    }

    // Индикаторы прогресса
    const progressContainer = document.getElementById('progress-container');
    const combinedProgress = document.getElementById('combined-progress');
    const transcriptionProgress = document.getElementById('transcription-progress');
    progressContainer.style.display = 'block';

    // Очищаем предыдущие результаты
    document.getElementById('transcription').querySelector('.content').innerText = 'Processing...';
    document.getElementById('summary').querySelector('.content').innerText = 'Processing...';

    try {
        let combinedPercent = 0;

        // --- Загрузка видео (симуляция) ---
        const downloadInterval = setInterval(() => {
            if (combinedPercent < 50) {
                combinedPercent += 1;
                updateProgress(combinedProgress, combinedPercent, "Загрузка видео...");
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


        clearInterval(downloadInterval);


        // --- Конвертация в аудио (симуляция) ---
        updateProgress(combinedProgress, combinedPercent, "Конвертация в аудио...");

        const convertInterval = setInterval(() => {
            if (combinedPercent < 100) {
                combinedPercent += 1;
                updateProgress(combinedProgress, combinedPercent, "Конвертация в аудио...");
            } else {
                clearInterval(convertInterval);
                updateProgress(combinedProgress, combinedPercent, "Обработка...");
            }
        }, 50);


        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Network response was not ok');
        }

        const data = await response.json();



        clearInterval(convertInterval); // Stop convert simulation


        updateProgress(transcriptionProgress, 0, "Транскрибация...");


        document.getElementById('transcription').querySelector('.content').innerText = data.transcription;
        document.getElementById('summary').querySelector('.content').innerText = data.summary;
        updateProgress(transcriptionProgress, 100, "Транскрибация завершена");  // Update transcription progress to 100%


    } catch (error) {
        console.error('Error details:', error);
        alert(`Error processing video: ${error.message}`);
        document.getElementById('transcription').querySelector('.content').innerText = 'Error occurred: ' + error.message;
        document.getElementById('summary').querySelector('.content').innerText = 'Processing failed. Please try again.';
    } finally {
        setTimeout(() => {
            progressContainer.style.display = 'none';
            updateProgress(combinedProgress, 0, "");
            updateProgress(transcriptionProgress, 0, "");

        }, 2000);
    }
}

function updateProgress(progressBar, percent, text = "") {
    if (progressBar) {
        progressBar.style.width = `${percent}%`;
        progressBar.innerText = text || `${percent}%`;
    }
}
