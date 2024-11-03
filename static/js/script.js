// Функция для копирования текста
function copyText(elementId) {
   try {
       // Находим контейнер с текстом
       const textContainer = document.getElementById(elementId).querySelector('.content');
       const text = textContainer.innerText;
       
       // Копируем текст в буфер обмена
       navigator.clipboard.writeText(text).then(() => {
           // Находим кнопку
           const copyButton = document.getElementById(elementId).querySelector('.copy-btn');
           
           // Меняем текст кнопки на "Copied!"
           const originalText = copyButton.innerText;
           copyButton.innerText = 'Copied!';
           copyButton.classList.add('btn-success');
           copyButton.classList.remove('btn-secondary');
           
           // Возвращаем оригинальный текст через 2 секунды
           setTimeout(() => {
               copyButton.innerText = originalText;
               copyButton.classList.remove('btn-success');
               copyButton.classList.add('btn-secondary');
           }, 2000);
       }).catch(err => {
           console.error('Failed to copy text:', err);
           alert('Failed to copy text to clipboard');
       });
   } catch (err) {
       console.error('Copy error:', err);
       alert('Failed to copy text');
   }
}

async function processVideo() {
   const url = document.getElementById('tiktokUrl').value;
   const lang = document.getElementById('language').value;
   
   if (!url) {
       alert('Please enter TikTok URL');
       return;
   }
   
   // Show progress container
   const progressContainer = document.getElementById('progress-container');
   progressContainer.style.display = 'block';
   
   // Progress bar elements
   const downloadProgress = document.getElementById('download-progress');
   const processProgress = document.getElementById('process-progress');
   
   // Initialize progress bars
   updateProgress(downloadProgress, 0);
   updateProgress(processProgress, 0);
   
   // Clear previous results
   document.getElementById('transcription').querySelector('.content').innerText = 'Processing...';
   document.getElementById('summary').querySelector('.content').innerText = 'Processing...';
   
   try {
       let combinedPercent = 0;
       
       // --- Download simulation ---
       const downloadInterval = setInterval(() => {
           if (combinedPercent < 50) {
               combinedPercent += 1;
               updateProgress(downloadProgress, combinedPercent); // Update download progress
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
       updateProgress(downloadProgress, 100);  // Set download progress to 100%
       
       // --- Processing simulation ---
       let processPercent = 0;
       const processInterval = setInterval(() => {
           if (processPercent < 100) {
               processPercent += 1;
               updateProgress(processProgress, processPercent); // Update processing progress
           } else {
               clearInterval(processInterval); // Stop processing simulation
           }
       }, 50);

       if (!response.ok) {
           const errorData = await response.json();
           throw new Error(errorData.detail || 'Network response was not ok');
       }

       const data = await response.json();
       
       // Update results
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
           updateProgress(downloadProgress, 0); // Reset download progress bar
           updateProgress(processProgress, 0); // Reset processing progress bar
       }, 2000);
   }
}

function updateProgress(progressBar, percent) {
   if (progressBar) {
       progressBar.style.width = `${percent}%`;
       progressBar.innerText = `${percent}%`;
   }
}

// Добавляем обработчики событий при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
   // Добавляем обработчики для кнопок копирования
   const transcriptionCopyBtn = document.querySelector('#transcription .copy-btn');
   const summaryCopyBtn = document.querySelector('#summary .copy-btn');
   
   if (transcriptionCopyBtn) {
       transcriptionCopyBtn.addEventListener('click', () => copyText('transcription'));
   }
   
   if (summaryCopyBtn) {
       summaryCopyBtn.addEventListener('click', () => copyText('summary'));
   }
});
