import { ElementHandle } from 'puppeteer';
import { platform } from 'os';

export async function speak(text: string): Promise<void> {
  const sayModule = await import('say');
  return new Promise((resolve, reject) => {
    sayModule.default.speak(text, undefined, 1.0, (err: string) => {
      if (err) reject(err);
      else resolve();
    });
  });
}

export function getElementDescription(element: ElementHandle | null): Promise<string> {
  if (!element) return Promise.resolve('No element selected');

  return element.evaluate((el) => {
    const tag = el.tagName.toLowerCase();
    const role = el.getAttribute('role');
    const ariaLabel = el.getAttribute('aria-label');
    const text = el.textContent?.trim() || '';

    let description = '';

    if (role) {
      description += `${role} `;
    }
    if (ariaLabel) {
      description += `${ariaLabel} `;
    }
    if (tag === 'a') {
      description += 'link ';
    } else if (tag === 'button') {
      description += 'button ';
    } else if (tag === 'input') {
      const type = el.getAttribute('type') || 'text';
      description += `${type} input `;
    }

    description += text;

    return description.trim();
  });
}

export async function checkDependencies(): Promise<void> {
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
