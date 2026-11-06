import asyncio, json, subprocess
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
        metrics = await page.evaluate("""
() => {
  const rect = (sel) => { const el = document.querySelector(sel); if (!el) return null; const r = el.getBoundingClientRect(); return {x:Math.round(r.x), y:Math.round(r.y), w:Math.round(r.width), h:Math.round(r.height), bottom:Math.round(r.bottom)}; };
  return {
    hdr: rect('#hdr'),
    tenant: rect('#session-tenant'),
    actor: rect('#session-actor'),
    brand: rect('.brand'),
    avatar: rect('.avatar')
  };
}
""")
        head = subprocess.check_output(["git","rev-parse","--short","HEAD"], text=True).strip()
        Path("/opt/cursor/artifacts").mkdir(parents=True, exist_ok=True)
        Path(f"/opt/cursor/artifacts/header_metrics_{head}.json").write_text(json.dumps(metrics, indent=2))
        print(json.dumps(metrics))
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())

