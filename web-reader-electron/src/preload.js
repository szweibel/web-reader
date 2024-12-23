const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('ipcRenderer', {
  processUrl: (url) => ipcRenderer.invoke('process-url', url),
  speak: (text) => ipcRenderer.invoke('speak', text),
  on: (channel, callback) => {
    ipcRenderer.on(channel, (event, ...args) => callback(...args));
  }
});
