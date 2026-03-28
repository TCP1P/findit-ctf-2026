const puppeteer = require('puppeteer');

const CONFIG = {
    APPNAME: process.env['APPNAME'] || "Admin",
    APPURL: process.env['APPURL'] || "http://localhost:9000",
    APPURLREGEX: process.env['APPURLREGEX'] || "^http(s|)://.*$",
    APPSECRET: process.env['APPSECRET'] || "secret-123",
    APPLIMITTIME: Number(process.env['APPLIMITTIME'] || "60"),
    APPLIMIT: Number(process.env['APPLIMIT'] || "5"),
}

console.table(CONFIG)

function sleep(s) {
    return new Promise((resolve) => setTimeout(resolve, s))
}

function generateRandomString(length) {
    let result = '';
    const characters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    const charactersLength = characters.length;
    for (let i = 0; i < length; i++) {
        result += characters.charAt(Math.floor(Math.random() * charactersLength));
    }
    return result;
}

const initBrowser = puppeteer.launch({
    executablePath: "/usr/bin/chromium-browser",
    headless: true,
    args: [
        '--disable-dev-shm-usage',
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-gpu',
        '--no-gpu',
        '--disable-default-apps',
        '--disable-translate',
        '--disable-device-discovery-notifications',
        '--disable-software-rasterizer',
        '--disable-xss-auditor',
    ],
    ipDataDir: '/home/bot/data/',
    ignoreHTTPSErrors: true
});

console.log("Bot started...");

module.exports = {
    name: CONFIG.APPNAME,
    urlRegex: CONFIG.APPURLREGEX,
    rateLimit: {
        windowS: CONFIG.APPLIMITTIME,
        max: CONFIG.APPLIMIT
    },
    bot: async (urlToVisit) => {
        const browser = await initBrowser;
        const context = await browser.createBrowserContext()
        try {
            // Goto main page
            const page = await context.newPage();
            const username = generateRandomString(32)
            const password = generateRandomString(32)

            console.log("username: ", username)
            console.log("password: ", password)

            // register
            await page.goto(`${CONFIG.APPURL}/register`)
            const registerUsernameInput = await page.waitForSelector("input[name='username']")
            await registerUsernameInput.type(username)
            const registerPasswordInput = await page.waitForSelector("input[name='password']")
            await registerPasswordInput.type(password)
            const registerSubmit = await page.waitForSelector("button")
            await registerSubmit.click()
            await sleep(500)

            // login
            await page.goto(`${CONFIG.APPURL}/login`)
            const loginUsernameInput = await page.waitForSelector("input[name='username']")
            await loginUsernameInput.type(username)
            const loginPasswordInput = await page.waitForSelector("input[name='password']")
            await loginPasswordInput.type(password)
            await Promise.all([
                page.waitForNavigation({ waitUntil: "domcontentloaded", timeout: 30000 }),
                page.evaluate(() => {
                    const form = document.querySelector("form[action='/login'], form");
                    if (!form) {
                        throw new Error("login form not found");
                    }

                    const submit = form.querySelector("button[type='submit'], button");
                    if (submit) {
                        submit.disabled = false;
                    }

                    form.submit();
                }),
            ]);
            await sleep(500)

            // add flag to note
            await page.goto(`${CONFIG.APPURL}`)
            const contentInput = await page.waitForSelector("textarea")
            await contentInput.type(`${CONFIG.APPSECRET} <!--secret-->`)
            const noteSubmit = await page.waitForSelector("button")
            await noteSubmit.click()
            await sleep(500)


            // Visit URL from user
            console.log(`bot visiting ${urlToVisit}`)
            await page.goto(urlToVisit, {
                waitUntil: 'networkidle2'
            });

            await sleep(120*1000)

            // Close
            console.log("browser close...")
            await context.close()
            return true;
        } catch (e) {
            console.error(e);
            await context.close();
            return false;
        }
    }
}
