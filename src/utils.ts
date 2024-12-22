import { HTMLElement } from 'node-html-parser';
import { execSync } from 'child_process';

export async function speak(text: string): Promise<void> {
  return new Promise((resolve, reject) => {
    try {
      // Write text to a temporary file that festival can read
      const tempFile = '/tmp/festival-text.txt';
      execSync(`echo "${text}" > ${tempFile}`);
      // Use festival to speak the text
      execSync(`festival --tts ${tempFile}`);
      // Clean up
      execSync(`rm ${tempFile}`);
      resolve();
    } catch (error) {
      reject(error);
    }
  });
}

export function getElementDescription(element: HTMLElement | null): string {
  if (!element) return 'No element selected';

  const tag = element.tagName.toLowerCase();
  const role = element.getAttribute('role');
  const ariaLabel = element.getAttribute('aria-label');
  const text = element.textContent.trim();

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
    const type = element.getAttribute('type') || 'text';
    description += `${type} input `;
  }

  description += text;

  return description.trim();
}

export async function checkDependencies(): Promise<void> {
  console.error('Checking system dependencies...');
  
  // Check for Chrome dependencies
  try {
    const puppeteer = await import('puppeteer');
    await puppeteer.default.launch();
    console.error('✓ Puppeteer/Chrome dependencies OK');
  } catch (error) {
    console.error('✗ Missing Chrome dependencies. Please install with:');
    console.error('sudo apt-get install -y chromium-browser');
    process.exit(1);
  }

  // Check for speech dependencies
  try {
    execSync('which festival');
    console.error('✓ Text-to-speech dependencies OK');
  } catch (error) {
    console.error('✗ Missing text-to-speech dependencies. Please install with:');
    console.error('sudo apt-get install -y festival festvox-us-slt-hts');
    process.exit(1);
  }
}
