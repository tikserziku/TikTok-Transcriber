function updateProgress(downloadProgress, processProgress) {
    document.getElementById('download-progress').style.width = downloadProgress + '%';
    document.getElementById('download-progress').innerText = downloadProgress + '%';
    
    document.getElementById('process-progress').style.width = processProgress + '%';
    document.getElementById('process-progress').innerText = processProgress + '%';
}

async function processVideo() {
    const url = document.getElementById('tiktokUrl').value;
    const lang = document.getElementById('language').value;
    
    if (!url) {
        alert('Please enter TikTok URL');
        return;
    }

    document.getElementById('progress-container').style.display = 'block';
    updateProgress(0, 0);
    
    document.getElementById('transcription').querySelector('.content').innerText = 'Processing...';
    document.getElementById('summary').querySelector('.content').innerText = 'Processing...';
    
    try {
        let downloadProgress = 0;
        let processProgress = 0;
        const progressInterval = setInterval(() => {
            if (downloadProgress < 90) {
                downloadProgress += 10;
                updateProgress(downloadProgress, processProgress);
            }
        }, 500);

        const response = await fetch('/process', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                url: url,
                target_language: lang
            })
        });
        
        clearInterval(progressInterval);
        updateProgress(100, 50);
        
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        
        const data = await response.json();
        
        updateProgress(100, 100);
        
        document.getElementById('transcription').querySelector('.content').innerText = 
            data.transcription || 'Transcription failed';
        document.getElementById('summary').querySelector('.content').innerText = 
            data.summary || 'Summary failed';

        setTimeout(() => {
            document.getElementById('progress-container').style.display = 'none';
        }, 2000);
        
    } catch (error) {
        alert('Error processing video: ' + error.message);
        document.getElementById('transcription').querySelector('.content').innerText = 'Error occurred';
        document.getElementById('summary').querySelector('.content').innerText = 'Error occurred';
        document.getElementById('progress-container').style.display = 'none';
    }
}

function copyText(elementId) {
    const text = document.getElementById(elementId).querySelector('.content').innerText;
    navigator.clipboard.writeText(text);
    
    const btn = document.getElementById(elementId).querySelector('.copy-btn');
    const originalText = btn.innerText;
    btn.innerText = 'Copied!';
    btn.classList.add('btn-success');
    btn.classList.remove('btn-secondary');
    
    setTimeout(() => {
        btn.innerText = originalText;
        btn.classList.remove('btn-success');
        btn.classList.add('btn-secondary');
    }, 2000);
}
