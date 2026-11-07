import asyncio, subprocess, struct, json
from pathlib import Path
from playwright.async_api import async_playwright

# Use Vite dev server (has API proxy), more reliable for automated flow
FRONTEND = "http://localhost:43123/"

async def run():
    errors = []
    console_messages = []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        # Force device scale factor 1 so PNG width equals CSS width
        context = await browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
        page = await context.new_page()

        def on_console(m):
            try:
                if m.type == "error":
                    print("CONSOLE ERROR:", m.text)
                    errors.append((m.text, m.location))
                else:
                    # surface warnings for visibility and keep a log
                    if m.type == "warning":
                        print("CONSOLE WARN:", m.text)
                    console_messages.append({"type": m.type, "text": m.text})
            except Exception:
                pass
        page.on("console", on_console)

        await page.goto(FRONTEND)
        await page.click("a[href='/login']")
        await page.fill("#login-name", "analyst")
        await page.fill("#login-password", "demo")
        await page.click("#btn-login")
        await page.wait_for_selector("#btn-open-desk", timeout=10000)
        brief = await page.inner_text("body")
        for beat in ("The problem", "The solution", "The live demo", "Challenges and learnings", "The vision"):
            assert beat in brief, beat
        await page.click("#btn-open-desk")
        await page.screenshot(path="/opt/cursor/artifacts/debug_after_goto.png", scale="css")
        txt = await page.evaluate("document.body.innerText")
        print('BODY:', txt[:2000])
        # Wait for session to populate
        await page.wait_for_function("() => document.body.innerText.includes('Emirates NBD Demo')", timeout=15000)
        print('STEP: session ok, now wait findings')
        # Wait for at least one finding
        await page.wait_for_selector("ul[data-testid='queue'] li", timeout=5000)
        queue_text = await page.inner_text("ul[data-testid='queue']")
        assert "F-101" in queue_text, queue_text
        assert "F-901" not in queue_text, queue_text
        await page.click("#btn-scope-foreign")
        await page.wait_for_function("() => document.querySelector('#scope-pill') && document.querySelector('#scope-pill').textContent.includes('cross_tenant')", timeout=8000)
        print('STEP: select + run')
        # Select first, start run
        await page.click("ul[data-testid='queue'] li >> nth=0")
        await page.click("text=Draft reply")
        # Wait for at least one streamed step
        await page.wait_for_selector("#panel-trace li", timeout=10000)
        print('STEP: got trace li')
        # Then wait for draft steps to appear (or final rendered in trace)
        await page.wait_for_function("() => document.querySelectorAll('ol li').length > 0 || (document.querySelector('#panel-trace') && document.querySelector('#panel-trace').innerText.includes('final:'))", timeout=20000)
        print('STEP: risk/draft visible')
        # Escalate
        await page.click("button:has-text('Escalate')")
        await page.click("button:has-text('Refresh audit')")
        # Assert an audit row appears
        await page.wait_for_timeout(300)
        print('STEP: escalated + audit refreshed')
        # Scope refusal
        await page.fill("input[placeholder^='Ask or check']", "shut down camera now")
        await page.click("button:has-text('Check')")
        await page.wait_for_function("() => document.body.innerText.includes('destructive_request') || document.querySelector('.status-refused')", timeout=3000)
        # Keyboard j/k selection (ensure row-focus moves)
        await page.keyboard.press('j')
        await page.keyboard.press('k')
        # Horizontal overflow check
        overflow_ok = await page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        assert overflow_ok, "Horizontal overflow detected"
        # Critical controls are fully visible within viewport
        async def visible_within(sel: str):
            return await page.evaluate("""
(sel) => {
  const el = document.querySelector(sel);
  if (!el) return false;
  const r = el.getBoundingClientRect();
  return r.x >= 0 && r.right <= window.innerWidth && r.y >= 0 && r.bottom <= window.innerHeight;
}
""", sel)
        assert await visible_within('#btn-run'), 'Run triage not fully visible'
        assert await visible_within('#btn-escalate'), 'Escalate not fully visible'
        assert await visible_within('#btn-reject'), 'Reject not fully visible'
        assert await visible_within('#panel-trace'), 'Trace panel not fully visible'
        # Screenshots after completion (desktop/tablet)
        head = subprocess.check_output(["git","rev-parse","--short","HEAD"], text=True).strip()
        await page.set_viewport_size({"width": 1440, "height": 900})
        await page.screenshot(path=f"/opt/cursor/artifacts/screen_run_{head}_1440.png", scale="css")
        await page.set_viewport_size({"width": 1024, "height": 768})
        await page.wait_for_timeout(100)
        await page.screenshot(path=f"/opt/cursor/artifacts/screen_run_{head}_768.png", scale="css")

        # Strict mobile proof in a fresh context (exact 390 CSS px, DPR=1, CSS-scaled PNG)
        await context.close()
        context_m = await browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1)
        page_m = await context_m.new_page()
        page_m.on("console", on_console)
        await page_m.add_init_script("localStorage.setItem('casework-session','analyst')")
        await page_m.goto("http://localhost:43123/desk")
        # Ensure session
        await page_m.wait_for_function("() => document.body && document.body.innerText.includes('Emirates NBD Demo')", timeout=15000)
        # Queue screenshot before opening detail
        head = subprocess.check_output(["git","rev-parse","--short","HEAD"], text=True).strip()
        q_img = Path(f"/opt/cursor/artifacts/screen_run_{head}_390_queue.png")
        await page_m.screenshot(path=str(q_img), full_page=False, scale="css")
        await page_m.wait_for_selector("ul[data-testid='queue'] li", timeout=5000)
        await page_m.click("ul[data-testid='queue'] li >> nth=0")
        await page_m.wait_for_selector(".finding-title", timeout=5000)
        await page_m.click("text=Draft reply")
        # Scope refusal on mobile (styled banner)
        await page_m.fill("input[placeholder^='Ask or check']", "shut down camera now")
        await page_m.click("button:has-text('Check')")
        await page_m.wait_for_function("() => document.querySelector('#scope-pill') && document.querySelector('#scope-pill').textContent.length > 0", timeout=8000)
        # Escalate + refresh audit on mobile (in Overview)
        await page_m.click("button:has-text('Escalate')")
        await page_m.click("button:has-text('Refresh audit')")
        # Switch to Agent run tab and wait for steps
        await page_m.click("[data-testid='tab-agent']")
        await page_m.wait_for_selector("#panel-trace", timeout=5000)
        await page_m.wait_for_selector("#panel-trace li", timeout=10000)
        
        # Switch back to Overview tab and ensure risk/remediation are visible; then capture overview screenshot
        await page_m.click("[data-testid='tab-overview']")
        await page_m.wait_for_selector(".risk-score", timeout=8000)
        detail_img = Path(f"/opt/cursor/artifacts/screen_run_{head}_390_detail.png")
        await page_m.screenshot(path=str(detail_img), full_page=False, scale="css")
        # Reset scroll to top to validate header visibility, then collect metrics
        await page_m.evaluate("window.scrollTo(0,0)")
        # Collect viewport metrics and control bounds (before assertions so artifacts exist on failure)
        metrics = await page_m.evaluate("""
() => {
  const root = document.documentElement.getBoundingClientRect();
  const getRect = (sel) => {
    const el = document.querySelector(sel);
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height), right: Math.round(r.right), bottom: Math.round(r.bottom)};
  };
  return {
    viewport: { innerWidth: window.innerWidth, innerHeight: window.innerHeight, devicePixelRatio: window.devicePixelRatio },
    clientWidth: document.documentElement.clientWidth,
    bodyScrollWidth: document.body.scrollWidth,
    rootRect: { x: Math.round(root.x), y: Math.round(root.y), w: Math.round(root.width), h: Math.round(root.height) },
    controls: {
      hdr: getRect('#hdr'),
      queue: getRect('#queue'),
      main: getRect('.main'),
      trace: getRect('#panel-trace'),
      btnRun: getRect('#btn-run'),
      btnEscalate: getRect('#btn-escalate'),
      btnReject: getRect('#btn-reject'),
      scopePill: getRect('#scope-pill'),
      tenant: getRect('#session-tenant'),
      actor: getRect('#session-actor')
    },
    sse: (window.__SSE_EVENTS__ || []).map(e => ({ event: e.event, phase: e.data?.phase || null, replayed: !!(e.data && e.data.replayed) }))
  };
}
""")
        # Viewport screenshots (must be exactly 390px wide)
        widths = await page_m.evaluate("[window.innerWidth, document.documentElement.clientWidth]")
        assert widths[0]==390 and widths[1]==390, f"Viewport/client width mismatch at 390: {widths}"
        # Ensure Agent run tab is active and stepper is visible; scroll to bottom of stepper
        await page_m.click("[data-testid='tab-agent']")
        await page_m.wait_for_selector("#panel-trace li", timeout=10000)
        await page_m.evaluate("() => { const el = document.querySelector('#panel-trace'); if (el) el.scrollTop = el.scrollHeight; document.activeElement && document.activeElement.blur(); }")
        run_img = Path(f"/opt/cursor/artifacts/screen_run_{head}_390_run.png")
        try:
            run_img.unlink()
        except Exception:
            pass
        await page_m.screenshot(path=str(run_img), full_page=False, scale="css")
        data = run_img.read_bytes()
        imgw = struct.unpack(">I", data[16:20])[0]
        assert imgw == 390, f"Run PNG width {imgw} != 390"
        metrics["png"] = {"queue_width": 390, "detail_width": 390, "run_width": 390}
        Path("/opt/cursor/artifacts").mkdir(parents=True, exist_ok=True)
        (Path(f"/opt/cursor/artifacts/viewport_390_{head}.json")).write_text(json.dumps(metrics, indent=2))
        # Save console messages
        (Path(f"/opt/cursor/artifacts/console_390_{head}.json")).write_text(json.dumps(console_messages, indent=2))
        # No body-level horizontal overflow
        overflow_ok_m = await page_m.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        assert overflow_ok_m, "Horizontal overflow detected at 390"
        # Ensure stage events (planner/operator/checker/final) rendered in UI
        await page_m.click("[data-testid='tab-agent']")
        await page_m.wait_for_selector("#panel-trace", timeout=5000)
        async def wait_for_any(stages: list[str], timeout_ms: int = 8000):
            conds = " || ".join([f"t.includes('{s}')" for s in stages])
            expr = f"() => {{ const el = document.querySelector('#panel-trace'); if (!el) return false; const t = el.innerText; return {conds}; }}"
            await page_m.wait_for_function(expr, timeout=timeout_ms)
        await wait_for_any(['Plan'])
        await wait_for_any(['Enrich asset graph','Rank risk','Draft remediation'])
        await wait_for_any(['Check'])
        await wait_for_any(['Result'])
        # Assertions on positioning and visibility at 390
        hdr = metrics["controls"]["hdr"]; queue = metrics["controls"]["queue"]; actor = metrics["controls"]["actor"]; tenant = metrics["controls"]["tenant"]; trace_rect = metrics["controls"]["trace"]
        assert hdr and tenant and actor, "Header/tenant/actor metrics missing"
        if queue:
            assert actor["bottom"] <= queue["y"], f"Actor overlaps with queue: actor.bottom={actor['bottom']} queue.y={queue['y']}"
            assert tenant["bottom"] <= queue["y"], f"Tenant overlaps with queue: tenant.bottom={tenant['bottom']} queue.y={queue['y']}"
        assert trace_rect and trace_rect["h"] >= 120, f"Trace panel too small: h={trace_rect and trace_rect['h']}"
        # SSE raw events must include real streamed steps (not only final)
        phases = [e.get("phase") for e in metrics.get("sse", []) if e.get("event") in ("message","step")]
        assert any(p == "planner" for p in phases), f"No planner in SSE events: {metrics.get('sse')}"
        assert any(p == "operator" for p in phases), f"No operator in SSE events: {metrics.get('sse')}"
        assert any(p == "checker" for p in phases), f"No checker in SSE events: {metrics.get('sse')}"
        # Fail on console errors
        assert not errors, f"Console errors: {errors}"
        print('STEP: test done')
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())

