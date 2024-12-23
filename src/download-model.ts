import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { createWriteStream } from 'fs';
import { get } from 'https';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const MODEL_DIR = path.join(__dirname, '..', 'models');
const MODEL_PATH = path.join(MODEL_DIR, 'llama-2-7b-chat.Q4_K_M.gguf');
const MODEL_URL = 'https://huggingface.co/TheBloke/Llama-2-7B-Chat-GGUF/resolve/main/llama-2-7b-chat.Q4_K_M.gguf';

async function downloadFile(url: string, dest: string): Promise<void> {
  return new Promise((resolve, reject) => {
    // Ensure directory exists
    const dir = path.dirname(dest);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }

    const file = createWriteStream(dest);
    let totalBytes = 0;
    let downloadedBytes = 0;

    get(url, (response) => {
      if (response.statusCode !== 200) {
        reject(new Error(`Failed to download: ${response.statusCode} ${response.statusMessage}`));
        return;
      }

      totalBytes = parseInt(response.headers['content-length'] || '0', 10);

      response.on('data', (chunk) => {
        downloadedBytes += chunk.length;
        const progress = (downloadedBytes / totalBytes) * 100;
        process.stdout.write(`\rDownloading model: ${progress.toFixed(1)}%`);
      });

      response.pipe(file);

      file.on('finish', () => {
        file.close();
        console.log('\nDownload complete!');
        resolve();
      });
    }).on('error', (err) => {
      fs.unlink(dest, () => {}); // Delete the file if download failed
      reject(err);
    });

    file.on('error', (err) => {
      fs.unlink(dest, () => {}); // Delete the file if save failed
      reject(err);
    });
  });
}

async function main() {
  if (fs.existsSync(MODEL_PATH)) {
    console.log('Model already exists, skipping download');
    return;
  }

  console.log('Downloading model...');
  try {
    await downloadFile(MODEL_URL, MODEL_PATH);
  } catch (error) {
    console.error('Error downloading model:', error);
    process.exit(1);
  }
}

main();
