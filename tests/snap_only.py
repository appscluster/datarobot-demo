import asyncio, subprocess, struct
from pathlib import Path
from playwright.async_api import async_playwright

FRONTEND = "http://localhost:43123/"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(viewport={"width":1440,"height":900}, device_scale_factor=1)
        page = await ctx.new_page()
        await page.goto(FRONTEND)
        await page.wait_for_function("() => document.body.innerText.includes('Acme (demo)')", timeout=15000)
        await page.wait_for_selector("ul[data-testid='queue'] li")
        await page.click("ul[data-testid='queue'] li >> nth=0")
        await page.click("text=Run triage")
        await page.wait_for_selector(".trace li", timeout=10000)
        await page.click("button:has-text('Escalate')")
        await page.click("button:has-text('Refresh audit')")
        head = subprocess.check_output(["git","rev-parse","--short","HEAD"], text=True).strip()
        await page.screenshot(path=f"/opt/cursor/artifacts/screen_run_{head}_1440.png", scale="css")
        # Mobile
        await ctx.close()
        ctxm = await browser.new_context(viewport={"width":390,"height":844}, device_scale_factor=1)
        pm = await ctxm.new_page()
        await pm.goto(FRONTEND)
        await pm.wait_for_function("() => document.body && document.body.innerText.includes('Acme (demo)')", timeout=15000)
        await pm.wait_for_selector("ul[data-testid='queue'] li")
        await pm.click("ul[data-testid='queue'] li >> nth=0")
        await pm.click("text=Run triage")
        await pm.wait_for_selector(".trace li", timeout=10000)
        await pm.evaluate("document.querySelector('.graph-disclosure')?.setAttribute('open','true')")
        top = Path(f"/opt/cursor/artifacts/screen_run_{head}_390_top.png")
        await pm.screenshot(path=str(top), scale="css")
        await pm.locator('#panel-trace').scroll_into_view_if_needed()
        tr = Path(f"/opt/cursor/artifacts/screen_run_{head}_390_trace.png")
        await pm.screenshot(path=str(tr), scale="css")
        await pm.locator('.graph-disclosure').scroll_into_view_if_needed()
        gr = Path(f"/opt/cursor/artifacts/screen_run_{head}_390_graph.png")
        await pm.screenshot(path=str(gr), scale="css")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())

