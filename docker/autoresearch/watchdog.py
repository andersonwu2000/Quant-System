"""Autoresearch Watchdog — runs alongside the agent container.

Checks every 60 seconds:
1. factor.py exists
2. results.tsv growing (stale = agent stuck)
3. evaluate.py checksum unchanged
4. No unexpected files in work/
5. Consecutive crash detection
6. Saturation + OOS decay detection
7. Disk usage
"""

import hashlib
import time
from datetime import datetime
from pathlib import Path

WORK_DIR = Path("/app/work")
CHECK_INTERVAL = 60
STALE_THRESHOLD = 1800  # 30 min


def sha256(path: Path) -> str:
    if not path.exists():
        return "MISSING"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    return len(path.read_text(encoding="utf-8", errors="ignore").strip().splitlines())


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def main():
    log("Watchdog started")

    eval_checksum = sha256(Path("/app/evaluate.py"))
    log(f"evaluate.py checksum: {eval_checksum[:16]}...")

    last_result_lines = count_lines(WORK_DIR / "results.tsv")
    last_update_time = time.time()
    consecutive_crashes = 0
    last_runlog_mtime = 0.0

    while True:
        time.sleep(CHECK_INTERVAL)

        # 1. factor.py existence
        if not (WORK_DIR / "factor.py").exists():
            log("WARNING: factor.py missing!")

        # 2. results.tsv growth
        current_lines = count_lines(WORK_DIR / "results.tsv")
        if current_lines > last_result_lines:
            last_result_lines = current_lines
            last_update_time = time.time()
            log(f"Progress: results.tsv has {current_lines} entries")
        elif time.time() - last_update_time > STALE_THRESHOLD:
            stale_min = int((time.time() - last_update_time) / 60)
            log(f"STALE: No new results for {stale_min} minutes")

        # 3. evaluate.py integrity
        current_eval = sha256(Path("/app/evaluate.py"))
        if current_eval != eval_checksum:
            log(f"ALERT: evaluate.py checksum changed! was={eval_checksum[:16]}, now={current_eval[:16]}")

        # 4. unexpected files
        expected = {"factor.py", "results.tsv", "run.log", ".git", ".gitignore", "__pycache__", "reports"}
        actual = {p.name for p in WORK_DIR.iterdir()} if WORK_DIR.exists() else set()
        unexpected = actual - expected
        if unexpected:
            log(f"WARNING: unexpected files in work/: {unexpected}")

        # 5. consecutive crash detection (use mtime to avoid false counts)
        run_log = WORK_DIR / "run.log"
        if run_log.exists():
            mtime = run_log.stat().st_mtime
            if mtime > last_runlog_mtime:
                last_runlog_mtime = mtime
                content = run_log.read_text(encoding="utf-8", errors="ignore")
                if "--- CRASH ---" in content:
                    consecutive_crashes += 1
                    log(f"WARNING: evaluate.py crashed ({consecutive_crashes} consecutive)")
                    if consecutive_crashes >= 5:
                        log("ALERT: 5+ consecutive crashes -- agent may be stuck in crash loop!")
                else:
                    consecutive_crashes = 0

        # 6. saturation + OOS decay detection
        results_path = WORK_DIR / "results.tsv"
        if results_path.exists():
            lines = results_path.read_text(
                encoding="utf-8", errors="ignore"
            ).strip().splitlines()[1:]  # skip header
            if len(lines) >= 50:
                recent = lines[-50:]
                discard_count = sum(1 for l in recent if "\tdiscard\t" in l)
                if discard_count >= 50:
                    log("ALERT: 50 consecutive discards -- factor space may be exhausted")
            # OOS decay: consecutive L4-pass but L5-fail
            l4_fail_l5 = 0
            for l in reversed(lines):
                if "L5 OOS fail" in l:
                    l4_fail_l5 += 1
                else:
                    break
            if l4_fail_l5 >= 10:
                log(f"ALERT: {l4_fail_l5} consecutive L4-pass-L5-fail -- possible OOS overfitting")

        # 7. disk usage
        total_size = sum(
            f.stat().st_size for f in WORK_DIR.rglob("*") if f.is_file()
        ) if WORK_DIR.exists() else 0
        if total_size > 100 * 1024 * 1024:
            log(f"WARNING: work/ size = {total_size / 1024 / 1024:.1f}MB")


if __name__ == "__main__":
    main()
