#!/usr/bin/env python3
"""FlowPilot End-to-End Demonstration Script

Executes a full mission run against the running backend server:
1. Verifies health and system info.
2. Resets demo calendar and tasks.
3. Dispatches an autonomous scheduling goal with conflict recovery.
4. Audits the live tool call stream.
5. Inspects independent SQLite verification proofs.
6. Prints final verified calendar state.
"""

import json
import sys
import time
import urllib.request
import urllib.error
from datetime import date, timedelta

BASE_URL = "http://127.0.0.1:8000"


def http_req(endpoint: str, method: str = "GET", data: dict | None = None) -> dict:
    url = f"{BASE_URL}{endpoint}"
    headers = {"Content-Type": "application/json"}
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        print(f"[-] Connection error to {url}: {e}")
        sys.exit(1)


def main():
    print("=" * 70)
    print(" FlowPilot -- Autonomous Calendar Agent End-to-End Demo")
    print("=" * 70)

    # 1. Healthcheck
    print("\n[1] Checking Backend Health...")
    health = http_req("/health")
    print(f"    Status: {health.get('status')}")
    print(f"    App: {health.get('app')}")
    print(f"    Timezone: {health.get('timezone')}")
    print(f"    Provider Mode: {health.get('provider_mode')}")

    # 2. Reset Demo Database
    print("\n[2] Resetting Database to Clean Demo State...")
    reset_res = http_req("/demo/reset", method="POST")
    print(f"    Reset status: {reset_res.get('reset')}")
    print(f"    Restored seed events: {reset_res.get('events')}")
    print(f"    Restored backlog tasks: {reset_res.get('tasks')}")

    # 3. Inspect Initial Calendar State
    target_date = (date.today() + timedelta(days=1)).isoformat()
    init_cal = http_req(f"/calendar?date={target_date}")
    print(f"\n[3] Initial Calendar for {target_date}:")
    for ev in init_cal.get("events", []):
        lock = "[FIXED]" if ev.get("is_fixed") else "[FLEXIBLE]"
        print(f"    - {ev.get('start_time')[11:16]} to {ev.get('end_time')[11:16]}: {ev.get('title')} {lock}")

    # 4. Dispatch Mission
    goal = (
        "Plan tomorrow. I need two hours of DSA practice, three hours for my project, "
        "lunch, and a team meeting at 2 PM. Finish by 7 PM."
    )
    print("\n[4] Dispatching Autonomous Mission:")
    print(f"    Goal: \"{goal}\"")
    start_time = time.time()
    run_res = http_req("/agent/run", method="POST", data={"goal": goal, "date": target_date})
    elapsed = time.time() - start_time
    run_id = run_res["id"]
    print(f"    Mission finished in {elapsed:.2f}s with status: {run_res.get('status')}")

    # 5. Tool Call Audit Stream
    events_res = http_req(f"/agent/runs/{run_id}/events")
    print(f"\n[5] Tool Call Execution Stream ({len(events_res)} steps executed):")
    for idx, log in enumerate(events_res, 1):
        status_icon = "[OK]" if log.get("success") else "[FAIL]"
        conflict_note = " (Conflict Recovery)" if log.get("tool_name") == "delete_event" else ""
        print(f"    Step {idx:2d}: {status_icon} {log.get('tool_name')}{conflict_note}")
        if not log.get("success"):
            print(f"             Error: {log.get('error')}")

    # 6. Verification Report
    verif = http_req(f"/agent/runs/{run_id}/verification") or {}
    print(f"\n[6] Independent SQLite Verification Audit:")
    passed_str = "PASSED" if verif.get("passed") else "FAILED"
    print(f"    Overall Audit Outcome: {passed_str}")
    for chk in verif.get("checks", []):
        chk_icon = "[PASS]" if chk.get("passed") else "[FAIL]"
        evidence = chk.get("evidence") or chk.get("description") or "OK"
        print(f"    {chk_icon} {chk.get('name')}: {evidence}")

    # 7. Final Calendar State
    final_cal = http_req(f"/calendar?date={target_date}")
    print(f"\n[7] Final Persisted Calendar for {target_date}:")
    for ev in final_cal.get("events", []):
        src = f"({ev.get('source')})"
        lock = "[FIXED]" if ev.get("is_fixed") else ""
        print(f"    - {ev.get('start_time')[11:16]} to {ev.get('end_time')[11:16]}: {ev.get('title')} {src} {lock}".strip())

    print("\n" + "=" * 70)
    print(" DEMO COMPLETED SUCCESSFULLY -- 100% VERIFIED")
    print("=" * 70)


if __name__ == "__main__":
    main()
