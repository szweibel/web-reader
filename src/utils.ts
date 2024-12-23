import { ElementHandle } from 'puppeteer';
import { platform } from 'os';
import say from 'say';

interface SpeechOptions {
  rate?: number;
  voice?: string;
  priority?: 'high' | 'normal' | 'low';
  interrupt?: boolean;
}

class SpeechQueue {
  private queue: Array<{ text: string; options: SpeechOptions; resolve: () => void; reject: (err: Error) => void }> = [];
  private speaking = false;
  private currentSpeech: { stop: () => void } | null = null;

  async speak(text: string, options: SpeechOptions = {}): Promise<void> {
    if (options.interrupt && this.speaking) {
      this.stop();
    }

    return new Promise((resolve, reject) => {
      const item = { text, options, resolve, reject };
      
      if (options.priority === 'high') {
        this.queue.unshift(item);
      } else if (options.priority === 'low') {
        this.queue.push(item);
      } else {
        // Insert after other high priority items
        const lastHighPriority = this.queue
          .map((i): boolean => i.options.priority === 'high')
          .lastIndexOf(true);
        if (lastHighPriority >= 0) {
          this.queue.splice(lastHighPriority + 1, 0, item);
        } else {
          this.queue.unshift(item);
        }
      }

      this.processQueue();
    });
  }

  private async processQueue(): Promise<void> {
    if (this.speaking || this.queue.length === 0) return;

    this.speaking = true;
    const { text, options, resolve, reject } = this.queue.shift()!;

    try {
      const rate = typeof options.rate === 'number' ? options.rate : 1.0;
      
      await new Promise<void>((res, rej) => {
        say.speak(
          text,
          options.voice,
          rate,
          (err: string) => {
            if (err) rej(new Error(err));
            else res();
          }
        );
      });
      
      resolve();
    } catch (error) {
      reject(error instanceof Error ? error : new Error(String(error)));
    } finally {
      this.speaking = false;
      this.currentSpeech = null;
      this.processQueue();
    }
  }

  async stop(): Promise<void> {
    say.stop();
    if (this.currentSpeech) {
      this.currentSpeech = null;
    }
  }

  async clear(): Promise<void> {
    this.queue = [];
    await this.stop();
  }
}

const speechQueue = new SpeechQueue();

export async function speak(text: string, options: SpeechOptions = {}): Promise<void> {
  // Ensure rate is passed through correctly
  const { rate = 1.0, ...rest } = options;
  return speechQueue.speak(text, { rate, ...rest });
}

export async function stopSpeech(): Promise<void> {
  await speechQueue.stop();
}

export async function clearSpeechQueue(): Promise<void> {
  await speechQueue.clear();
}

export function getElementDescription(element: ElementHandle | null): Promise<string> {
  if (!element) return Promise.resolve('No element selected');

  return element.evaluate((el) => {
    const tag = el.tagName.toLowerCase();
    const role = el.getAttribute('role');
    const ariaLabel = el.getAttribute('aria-label');
    const text = el.textContent?.trim() || '';

    let description = '';
    const type = el.getAttribute('type');
    const value = (el as HTMLInputElement).value;
    const disabled = el.getAttribute('disabled') !== null || el.getAttribute('aria-disabled') === 'true';

    if (tag === 'a') {
      description = `link: ${text}`;
    } else if (tag === 'button') {
      description = ariaLabel || text;
      if (disabled) {
        description += ' (disabled)';
      }
    } else if (tag === 'input') {
      description = `${type || 'text'} input`;
      if (value) {
        description += `: ${value}`;
      }
    } else {
      description = ariaLabel || role || text;
    }

    return description;
  });
}

export async function checkDependencies(): Promise<void> {
  // Skip dependency checks in test mode or if explicitly skipped
  if (process.env.NODE_ENV === 'test' || process.env.SKIP_DEPENDENCY_CHECK === '1') {
    return Promise.resolve();
  }

  console.error('Checking system dependencies...');
  
  // Check for Chrome/Puppeteer dependencies
  try {
    const puppeteer = await import('puppeteer');
    await puppeteer.default.launch();
    console.error('✓ Puppeteer/Chrome dependencies OK');
  } catch (error) {
    let installInstructions = '';
    switch (platform()) {
      case 'darwin':
        installInstructions = 'brew install chromium';
        break;
      case 'win32':
        installInstructions = 'Please download and install Chrome from https://www.google.com/chrome/';
        break;
      default: // Linux
        installInstructions = 'sudo apt-get install -y chromium-browser || sudo dnf install -y chromium';
    }
    console.error('✗ Missing Chrome dependencies. Please install with:');
    console.error(installInstructions);
    process.exit(1);
  }

  // Check text-to-speech dependencies
  if (platform() === 'darwin') {
    console.error('✓ Text-to-speech dependencies OK (using macOS say command)');
  } else if (platform() === 'win32') {
    console.error('✓ Text-to-speech dependencies OK (using Windows SAPI)');
  } else {
    try {
      await speak('Test');
      console.error('✓ Text-to-speech dependencies OK');
    } catch (error) {
      console.error('✗ Text-to-speech dependencies missing. Please install with:');
      console.error('sudo apt-get install -y festival festvox-us-slt-hts || sudo dnf install -y festival festvox-slt-hts');
      process.exit(1);
    }
  }
}
