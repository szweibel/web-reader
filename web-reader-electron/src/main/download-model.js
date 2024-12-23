const fs = require('fs');
const path = require('path');
const { createWriteStream } = require('fs');
const { get } = require('https');
const { app } = require('electron');

const MODEL_DIR = path.join(__dirname, '..', '..', 'models');
const MODEL_PATH = path.join(MODEL_DIR, 'llama-2-7b-chat.Q4_K_M.gguf');
const MODEL_URL = 'https://huggingface.co/TheBloke/Llama-2-7B-Chat-GGUF/resolve/main/llama-2-7b-chat.Q4_K_M.gguf';

async function downloadModel(progressCallback) {
  return new Promise((resolve, reject) => {
    if (fs.existsSync(MODEL_PATH)) {
      console.log('Model already exists');
      resolve(MODEL_PATH);
      return;
    }

    // Ensure directory exists
    if (!fs.existsSync(MODEL_DIR)) {
      fs.mkdirSync(MODEL_DIR, { recursive: true });
    }

    console.log('Downloading model...');
    const file = createWriteStream(MODEL_PATH);
    let totalBytes = 0;
    let downloadedBytes = 0;

    get(MODEL_URL, (response) => {
      if (response.statusCode === 302 || response.statusCode === 301) {
        // Handle redirect
        const redirectUrl = response.headers.location;
        if (!redirectUrl) {
          reject(new Error('Redirect location not found'));
          return;
        }
        get(redirectUrl, handleResponse).on('error', handleError);
        return;
      }
      
      handleResponse(response);
    }).on('error', handleError);

    function handleResponse(response) {
      if (response.statusCode !== 200) {
        reject(new Error(`Failed to download: ${response.statusCode} ${response.statusMessage}`));
        return;
      }

      totalBytes = parseInt(response.headers['content-length'] || '0', 10);

      response.on('data', (chunk) => {
        downloadedBytes += chunk.length;
        const progress = (downloadedBytes / totalBytes) * 100;
        if (progressCallback) {
          progressCallback(progress);
        }
      });

      response.pipe(file);

      file.on('finish', () => {
        file.close();
        console.log('\nDownload complete!');
        resolve(MODEL_PATH);
      });
    }

    function handleError(err) {
      fs.unlink(MODEL_PATH, () => {});
      reject(err);
    }

    file.on('error', handleError);
  });
}

function getModelPath() {
  return MODEL_PATH;
}

module.exports = {
  downloadModel,
  getModelPath
};
