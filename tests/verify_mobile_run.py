import asyncio, json, subprocess, time
from pathlib import Path
from playwright.async_api import async_playwright

FRONTEND = "http://localhost:43123/"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(viewport={"width":390,"height":844}, device_scale_factor=1)
        page = await ctx.new_page()
        await page.add_init_script("localStorage.setItem('casework-session','analyst')")
        await page.goto("http://localhost:43123/desk")
        await page.wait_for_function("() => document.body && document.body.innerText.includes('Emirates NBD Demo')", timeout=15000)
        await page.wait_for_selector("ul[data-testid='queue'] li", timeout=5000)
        await page.click("ul[data-testid='queue'] li >> nth=0")
        await page.click("text=Draft reply")
        await page.click("text=Agent run")
        # Wait for animations to settle, then small buffer
        await page.wait_for_function("() => (document.getAnimations ? document.getAnimations().length===0 : true)")
        await page.wait_for_timeout(300)
        # Assert active tab and visibility
        active_text = await page.evaluate("() => { const a=[...document.querySelectorAll('[role=tab][aria-selected=true]')].map(x=>x.textContent.trim()); return a.join(','); }")
        title_visible = await page.is_visible(".finding-title")
        # Wait for stepper to render at least one step
        await page.wait_for_selector("#panel-trace li .step-title", timeout=10000)
        # Collect step titles
        steps = await page.evaluate("""() => {
          const lis = [...document.querySelectorAll('#panel-trace li .step-title')];
          return lis.map(el => el.textContent.trim());
        }""")
        # Collect tab styles and aria-selected
        tabs = await page.evaluate("""() => {
          return [...document.querySelectorAll('[role=tab]')].map(el => {
            const cs = getComputedStyle(el);
            return { text: el.textContent.trim(), selected: el.getAttribute('aria-selected')==='true', bg: cs.backgroundColor };
          });
        }""")
        # Capture timestamped Agent run screenshot (scrolled to show final steps).
        # Also log elementFromPoint(195,130) and key rects to diagnose any top-gap.
        elem_info = await page.evaluate("""() => {
          const p = (sel) => { const el = document.querySelector(sel); if (!el) return null;
            const r = el.getBoundingClientRect(); return {sel, x:r.x, y:r.y, w:r.width, h:r.height, bottom:r.bottom}; };
          const efp = document.elementFromPoint(195,130);
          const er = efp ? efp.getBoundingClientRect() : null;
          return {
            efp: efp ? { tag: efp.tagName, cls: efp.className, rect: er && {x:er.x, y:er.y, w:er.width, h:er.height} } : null,
            header: p('#hdr'),
            panelTrace: p('#panel-trace'),
            mainBody: p('.main-body'),
            scrollY: window.scrollY
          };
        }""")
        await page.evaluate("() => { const el = document.querySelector('#panel-trace'); if (el) el.scrollTop = el.scrollHeight; document.activeElement && document.activeElement.blur(); }")
        head = subprocess.check_output(["git","rev-parse","--short","HEAD"], text=True).strip()
        epoch = int(time.time())
        Path("/opt/cursor/artifacts").mkdir(parents=True, exist_ok=True)
        run_out = Path(f"/opt/cursor/artifacts/screen_390_run_{head}_{epoch}.png")
        await page.screenshot(path=str(run_out), full_page=False, scale="css")
        # Switch to Overview and capture a timestamped detail screenshot
        await page.click("[data-testid='tab-overview']")
        await page.wait_for_function("() => (document.getAnimations ? document.getAnimations().length===0 : true)")
        await page.wait_for_timeout(300)
        await page.wait_for_selector(".finding-title", timeout=5000)
        detail_out = Path(f"/opt/cursor/artifacts/screen_390_detail_{head}_{epoch}.png")
        await page.screenshot(path=str(detail_out), full_page=False, scale="css")
        # Assert overview tab highlighted and run tab not highlighted
        overview_ok = await page.evaluate("""() => {
          const tabs = [...document.querySelectorAll('[role=tab]')];
          const t = (s) => tabs.find(x => x.textContent.trim()===s);
          const ov = t('Overview'), ar = t('Agent run');
          if (!ov || !ar) return false;
          const ovBg = getComputedStyle(ov).backgroundColor;
          const arBg = getComputedStyle(ar).backgroundColor;
          const isAccent = (c) => /rgb\\(19,\\s*160,\\s*148\\)/.test(c);
          return isAccent(ovBg) && !isAccent(arBg);
        }""")
        # Open a 1024x768 context and capture a timestamped 768 screenshot (post-run state is acceptable)
        ctx2 = await browser.new_context(viewport={"width":1024,"height":768}, device_scale_factor=1)
        page2 = await ctx2.new_page()
        await page2.add_init_script("localStorage.setItem('casework-session','analyst')")
        await page2.goto("http://localhost:43123/desk")
        await page2.wait_for_function("() => document.body && document.body.innerText.includes('Emirates NBD Demo')", timeout=15000)
        await page2.wait_for_selector("ul[data-testid='queue'] li", timeout=5000)
        await page2.click("ul[data-testid='queue'] li >> nth=0")
        await page2.click("text=Draft reply")
        await page2.wait_for_selector("#panel-trace li .step-title", timeout=10000)
        snap_768 = Path(f"/opt/cursor/artifacts/screen_768_{head}_{epoch}.png")
        await page2.screenshot(path=str(snap_768), full_page=False, scale="css")
        await ctx2.close()
        info = {
          "active_tab": active_text,
          "finding_title_visible": title_visible,
          "step_titles": steps,
          "tabs": tabs,
          "diagnostics": elem_info,
          "overview_tab_matches_panel": bool(overview_ok),
          "captures": {
            "run_png": str(run_out),
            "detail_png": str(detail_out),
            "snap_768": str(snap_768)
          }
        }
        Path(f"/opt/cursor/artifacts/mobile_run_check_{head}.json").write_text(json.dumps(info, indent=2))
        print(json.dumps(info))
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())

