import json
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
from playwright.async_api import async_playwright

app = FastAPI()

class ExecuteRequest(BaseModel):
    command: str

@app.get("/", summary="Health Check")
async def health_check():
    """A simple health check endpoint to confirm the server is running."""
    return {"status": "ok", "message": "Sandbox Runtime is active."}

@app.post("/execute")
async def execute_command(req: ExecuteRequest):
    try:
        url = req.command

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, timeout=15000)
            content = await page.evaluate("document.body.innerText")
            await browser.close()

            success_output = json.dumps({"status": "success", "content": content[:2000]})

            return {
                "stdout": success_output,
                "stderr": "",
                "exitCode": 0
            }

    except Exception as e:
        error_output = json.dumps({"status": "error", "message": str(e)})

        return {
            "stdout": "",
            "stderr": error_output,
            "exitCode": 1
        }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
