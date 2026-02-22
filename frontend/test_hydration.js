const puppeteer = require('puppeteer');

(async () => {
  console.log("Launching browser...");
  const browser = await puppeteer.launch({ headless: 'new' });
  const page = await browser.newPage();
  
  page.on('console', msg => {
    if (msg.type() === 'error' && msg.text().includes('Hydration') || msg.text().includes('did not match')) {
      console.log('HYDRATION ERROR:', msg.text());
    }
  });

  page.on('pageerror', err => {
    console.log('PAGE ERROR:', err.message);
  });

  console.log("Navigating to http://localhost:3000...");
  await page.goto('http://localhost:3000', { waitUntil: 'networkidle0', timeout: 30000 }).catch(e => console.log(e));
  
  console.log("Navigating to http://localhost:3000/accounts...");
  await page.goto('http://localhost:3000/accounts', { waitUntil: 'networkidle0', timeout: 30000 }).catch(e => console.log(e));

  await browser.close();
  console.log("Done.");
})();
