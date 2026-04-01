import sys
import json
import asyncio
from playwright.async_api import async_playwright

async def main(url: str):
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, timeout=15000)
            content = await page.evaluate("document.body.innerText")
            await browser.close()

            print(json.dumps({"status": "success", "content": content[:2000]}))
    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"status": "error", "message": "No URL provided"}))
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
