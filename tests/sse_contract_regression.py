import asyncio, json, time, subprocess
from pathlib import Path
import httpx

ART = Path("/opt/cursor/artifacts")
ART.mkdir(parents=True, exist_ok=True)

async def stream_sse(client: httpx.AsyncClient, run_id: str, delay_s: float, max_sec: float):
    if delay_s:
        await asyncio.sleep(delay_s)
    url = f"http://127.0.0.1:54123/runs/{run_id}/events"
    lines = []
    t0 = time.time()
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
            if time.time() - t0 > max_sec:
                break
    return lines

def parse_seq(lines):
    seqs = []
    phases = []
    has_final = False
    for ln in lines:
        if not ln.startswith("data: "):
            continue
        try:
            obj = json.loads(ln[6:])
        except Exception:
            continue
        if "seq" in obj:
            seqs.append(int(obj["seq"]))
        if "phase" in obj:
            phases.append(obj["phase"])
        if obj.get("final") is True:
            has_final = True
    return seqs, phases, has_final

async def main():
    head = subprocess.check_output(["git","rev-parse","--short","HEAD"], text=True).strip()
    raw_path = ART / f"raw-SSE_{head}.txt"
    report_path = ART / f"test-report_{head}.txt"
    lines_out = []
    with open(report_path, "w") as rpt:
        async with httpx.AsyncClient(timeout=15) as c:
            # Early subscriber scenario (new run A)
            r = await c.post("http://127.0.0.1:54123/api/runs", json={"finding_id":"F-101"})
            run_a = r.json()["run_id"]
            early = await stream_sse(c, run_a, delay_s=0.0, max_sec=10.0)
            # Late subscriber scenario (new run B)
            r = await c.post("http://127.0.0.1:54123/api/runs", json={"finding_id":"F-101"})
            run_b = r.json()["run_id"]
            late = await stream_sse(c, run_b, delay_s=0.6, max_sec=10.0)
        # Save raw
        lines_out.append("=== EARLY ===")
        lines_out.extend(early)
        lines_out.append("=== LATE ===")
        lines_out.extend(late)
        raw_path.write_text("\n".join(lines_out))
        # Analyze
        e_seqs, e_phases, e_final = parse_seq(early)
        l_seqs, l_phases, l_final = parse_seq(late)
        # Assertions
        def is_strictly_increasing(xs): return all(xs[i] < xs[i+1] for i in range(len(xs)-1))
        early_ok = (len(e_seqs) >= 7 and is_strictly_increasing(e_seqs)
                    and "planner" in e_phases and "checker" in e_phases and e_final)
        late_ok = (len(l_seqs) >= 7 and is_strictly_increasing(l_seqs)
                    and "planner" in l_phases and "checker" in l_phases and l_final)
        rpt.write(f"HEAD {head}\n")
        rpt.write(f"early_run_id {run_a}\nlate_run_id {run_b}\n")
        rpt.write(f"early_seqs {e_seqs}\nearly_phases {e_phases}\nearly_final {e_final}\n")
        rpt.write(f"late_seqs {l_seqs}\nlate_phases {l_phases}\nlate_final {l_final}\n")
        exit_code = 0
        if not early_ok or not late_ok:
            exit_code = 1
            rpt.write("RESULT: FAIL\n")
        else:
            rpt.write("RESULT: PASS\n")
    print(str(report_path))
    print(str(raw_path))
    return 0

if __name__ == "__main__":
    asyncio.run(main())

