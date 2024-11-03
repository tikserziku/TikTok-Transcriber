async function processVideo() {
    const url = document.getElementById('tiktokUrl').value;
    const lang = document.getElementById('language').value;

    if (!url) {
        alert('Please enter TikTok URL');
        return;
    }

    // Показываем прогресс
    const progressContainer = document.getElementById('progress-container');
    const progressBar = document.getElementById('progress-bar');
    progressContainer.style.display = 'block';
    updateProgress(0); // Initialize progress bar

    // Очищаем предыдущие результаты
    document.getElementById('transcription').querySelector('.content').innerText = 'Processing...';
    document.getElementById('summary').querySelector('.content').innerText = 'Processing...';

    try {
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

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Network response was not ok');
        }

        // Read the response stream in chunks to update progress
        const reader = response.body.getReader();
        const contentLength = +response.headers.get('Content-Length'); // Total size
        let receivedLength = 0; // Bytes received so far
        let chunks = [];

        while (true) {
            const { done, value } = await reader.read();

            if (done) {
                break;
            }

            chunks.push(value);
            receivedLength += value.length;
            updateProgress(parseInt(receivedLength / contentLength * 100));
        }




        const chunksAll = new Uint8Array(receivedLength); // (4.1)
        let position = 0;
        for(let chunk of chunks) {
            chunksAll.set(chunk, position); // (4.2)
            position += chunk.length;
        }


        let textData = new TextDecoder("utf-8").decode(chunksAll);
        let data = JSON.parse(textData);



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
            updateProgress(0);
        }, 2000);
    }
}


function updateProgress(percent) {
    const progressBar = document.getElementById('progress-bar');
    if(progressBar) {
        progressBar.style.width = `${percent}%`;
        progressBar.innerText = `${percent}%`;
    }
}
