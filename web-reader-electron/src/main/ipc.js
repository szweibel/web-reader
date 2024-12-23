const { ipcMain } = require('electron');
const { LLMManager } = require('./llm');

async function setupIPC(llm) {
  console.log('Setting up IPC handlers...');
  
  ipcMain.handle('process-url', async (event, url) => {
    console.log('process-url called with:', url);
    try {
      if (!llm) {
        throw new Error('LLM manager not initialized');
      }
      const description = await llm.enhanceDescription(url);
      return {
        description,
        suggestions: await llm.suggestNavigation(url, 'explore page')
      };
    } catch (error) {
      console.error('Error processing URL:', error);
      throw new Error(error?.message || 'Failed to process URL');
    }
  });

  ipcMain.handle('speak', async (event, text) => {
    console.log('speak called with:', text);
    // Use system text-to-speech
    if (process.platform === 'darwin') {
      const { exec } = require('child_process');
      exec(`say "${text.replace(/"/g, '\\"')}"`);
    }
  });
}

module.exports = { setupIPC };
