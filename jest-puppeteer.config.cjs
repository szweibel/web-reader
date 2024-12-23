/** @type {import('jest-environment-puppeteer').JestPuppeteerConfig} */
module.exports = {
  launch: {
    headless: 'new',
    args: ['--no-sandbox', '--disable-gpu'],
    timeout: 30000
  }
};
