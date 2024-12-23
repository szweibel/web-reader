export {};

declare global {
  interface Window {
    ipcRenderer: {
      processUrl: (url: string) => Promise<{
        description: string;
        suggestions: string;
      }>;
      speak: (text: string) => Promise<void>;
      on: (channel: string, callback: (...args: any[]) => void) => void;
    };
  }
}
