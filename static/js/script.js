async function processVideo() {
    const url = document.getElementById('tiktokUrl').value;
    const lang = document.getElementById('language').value;
    
    if (!url) {
        alert('Please enter TikTok URL');
        return;
    }

    // Показываем прогресс
    document.getElementById('progress-container').style.display = 'block';
    updateProgress(0, 0);
    
    // Очищаем предыдущие результаты
    document.getElementById('transcription').querySelector('.content').innerText = 'Processing...';
    document.getElementById('summary').querySelector('.content').innerText = 'Processing...';
    
    try {
        let downloadProgress = 0;
        let processProgress = 0;
        const progressInterval = setInterval(() => {
            if (downloadProgress < 90) {
                downloadProgress += 5;
                updateProgress(downloadProgress, processProgress);
            }
        }, 1000);

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
        
        clearInterval(progressInterval);
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Network response was not ok');
        }
        
        const data = await response.json();
        
        // Проверяем данные
        if (!data.transcription || !data.summary) {
            throw new Error('Invalid response data');
        }
        
        updateProgress(100, 100);
        
        document.getElementById('transcription').querySelector('.content').innerText = 
            data.transcription;
        document.getElementById('summary').querySelector('.content').innerText = 
            data.summary;

    } catch (error) {
        console.error('Error details:', error);
        alert(`Error processing video: ${error.message}`);
        document.getElementById('transcription').querySelector('.content').innerText = 
            'Error occurred: ' + error.message;
        document.getElementById('summary').querySelector('.content').innerText = 
            'Processing failed. Please try again.';
    } finally {
        // Скрываем прогресс через 2 секунды
        setTimeout(() => {
            document.getElementById('progress-container').style.display = 'none';
            updateProgress(0, 0);
        }, 2000);
    }
}
