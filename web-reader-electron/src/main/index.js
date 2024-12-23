const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const { LLMManager } = require('./llm');
const { setupIPC } = require('./ipc');

class WebReader {
  constructor() {
    this.window = null;
    this.llm = new LLMManager();
  }

  async init() {
    try {
      await this.llm.init();
      this.createWindow();
      setupIPC(this.llm);
    } catch (error) {
      console.warn('LLM initialization failed:', error);
      console.log('Continuing without LLM features');
      this.createWindow();
      setupIPC(null);
    }
  }

  createWindow() {
    this.window = new BrowserWindow({
      width: 800,
      height: 600,
      title: 'Web Reader - Accessible Web Browser',
      webPreferences: {
        preload: path.join(__dirname, '..', 'preload.js'),
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: true
      }
    });

    this.window.loadFile(path.join(__dirname, '../renderer/index.html'));

    // Open DevTools for debugging
    this.window.webContents.openDevTools();

    this.window.webContents.on('did-finish-load', () => {
      this.window?.webContents.send('app-ready');
    });

    // Enable keyboard navigation
    this.window.webContents.on('before-input-event', (event, input) => {
      // Handle keyboard navigation here
      if (input.key === 'Escape') {
        this.window?.webContents.send('stop-speaking');
      }
    });

    this.window.on('closed', () => {
      this.window = null;
    });
  }
}

const webReader = new WebReader();

app.on('ready', async () => {
  try {
    await webReader.init();
  } catch (error) {
    console.error('Error initializing app:', error);
  }
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (webReader.window === null) {
    webReader.createWindow();
  }
});

module.exports = WebReader;
