import say from 'say';
import { promisify } from 'util';
import { exec } from 'child_process';

const execAsync = promisify(exec);

// Promisify say functions
const speakAsync = (text: string) => new Promise<void>((resolve, reject) => {
  say.speak(text, undefined, undefined, (err) => {
    if (err) reject(err);
    else resolve();
  });
});

let isSpeaking = false;
let speakQueue: string[] = [];

/**
 * Check if required system dependencies are installed
 */
export async function checkDependencies(): Promise<void> {
  try {
    // Check for say command
    await execAsync('which say');
  } catch (error) {
    throw new Error('Text-to-speech command not found. Please ensure "say" is installed.');
  }
}

/**
 * Speak text using text-to-speech
 * @param text Text to speak
 */
export async function speak(text: string): Promise<void> {
  // Add to queue
  speakQueue.push(text);
  
  // If already speaking, return (text will be spoken when current speech finishes)
  if (isSpeaking) {
    return;
  }

  // Process queue
  await processQueue();
}

/**
 * Process the speech queue
 */
async function processQueue(): Promise<void> {
  // If queue is empty or already speaking, return
  if (speakQueue.length === 0 || isSpeaking) {
    return;
  }

  // Get next text to speak
  const text = speakQueue.shift();
  if (!text) return;

  try {
    isSpeaking = true;
    await speakAsync(text);
  } catch (error) {
    console.error('Speech error:', error);
  } finally {
    isSpeaking = false;
    // Process next item in queue
    await processQueue();
  }
}

/**
 * Stop current speech
 */
export async function stopSpeaking(): Promise<void> {
  // Clear queue
  speakQueue = [];
  
  // Stop current speech
  if (isSpeaking) {
    try {
      say.stop();
      isSpeaking = false;
    } catch (error) {
      console.error('Error stopping speech:', error);
    }
  }
}
