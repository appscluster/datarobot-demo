import asyncio, json, time
from pathlib import Path
import httpx

ART_DIR = Path("/opt/cursor/artifacts")
ART_DIR.mkdir(parents=True, exist_ok=True)

async def collect_sse(client: httpx.AsyncClient, run_id: str, delay_s: float = 0.0) -> list[str]:
    if delay_s:
        await asyncio.sleep(delay_s)
    url = f"http://127.0.0.1:54123/runs/{run_id}/events"
    lines: list[str] = []
    async with client.stream("GET", url, headers={"Accept": "text/event-stream"}) as resp:
        async for line in resp.aiter_lines():
            if not line:
                continue
            lines.append(line)
            if line.startswith("data: "):
                try:
                    obj = json.loads(line[6:])
                    if obj.get("event") == "done":
                        break
                except Exception:
                    pass
    return lines

async def main():
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post("http://127.0.0.1:54123/api/runs", json={"finding_id": "F-101"})
        r.raise_for_status()
        run_id = r.json()["run_id"]
        # Early subscriber (immediate)
        early = asyncio.create_task(collect_sse(c, run_id, delay_s=0.0))
        # Delayed subscriber (replay)
        late = asyncio.create_task(collect_sse(c, run_id, delay_s=0.8))
        early_lines, late_lines = await asyncio.gather(early, late)
        head = Path.cwd().joinpath(".git").exists()
        head_short = "HEAD"
        try:
            import subprocess
            head_short = subprocess.check_output(["git","rev-parse","--short","HEAD"], text=True).strip()
        except Exception:
            pass
        out = ART_DIR / f"sse_regression_{head_short}.txt"
        with out.open("w") as f:
            f.write("=== EARLY ===\n")
            f.write("\n".join(early_lines) + "\n")
            f.write("\n=== LATE ===\n")
            f.write("\n".join(late_lines) + "\n")
        print(str(out))

if __name__ == "__main__":
    asyncio.run(main())

