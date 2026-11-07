import asyncio, subprocess
from pathlib import Path
from playwright.async_api import async_playwright

FRONTEND = "http://localhost:43123/"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(viewport={"width":1440,"height":900}, device_scale_factor=1)
        page = await ctx.new_page()
        await page.add_init_script("localStorage.setItem('casework-session','analyst')")
        await page.goto("http://localhost:43123/desk")
        await page.wait_for_function("() => document.body.innerText.includes('Emirates NBD Demo')", timeout=15000)
        await page.wait_for_selector("ul[data-testid='queue'] li", timeout=5000)
        await page.click("ul[data-testid='queue'] li >> nth=0")
        await page.click("text=Draft reply")
        # Wait for final step to exist
        await page.wait_for_function("() => document.querySelector('#panel-trace') && document.querySelector('#panel-trace').innerText.includes('Result')", timeout=15000)
        # Refresh audit so timeline is populated
        try:
            await page.click("button:has-text('Refresh')")
            await page.wait_for_selector(".audit-list li", timeout=4000)
        except Exception:
            pass
        # Scroll center column to bottom of stepper explicitly
        await page.evaluate("""() => {
          const step = document.querySelector('#panel-trace');
          if (step) { step.scrollTop = step.scrollHeight; step.scrollIntoView({block:'end'}); }
          const mainBody = document.querySelector('.main-body');
          if (mainBody) mainBody.scrollTop = mainBody.scrollHeight;
          window.scrollTo(0, 0);
        }""")
        head = subprocess.check_output(["git","rev-parse","--short","HEAD"], text=True).strip()
        out = Path(f"/opt/cursor/artifacts/screen_run_{head}_1440_bottom.png")
        await page.screenshot(path=str(out), scale="css")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())

