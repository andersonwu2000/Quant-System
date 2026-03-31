#!/bin/bash
# Quick research status check
LEARNINGS="D:/Finance/docker/autoresearch/watchdog_data/learnings.jsonl"
TOTAL=$(wc -l < "$LEARNINGS" 2>/dev/null || echo 0)
LAST5=$(tail -5 "$LEARNINGS" 2>/dev/null | python -c "
import sys, json
for line in sys.stdin:
    try:
        d = json.loads(line)
        ts = d.get('ts','?')[11:16]
        level = d.get('level','?')
        direction = d.get('direction','?')[:50]
        print(f'  {ts} {level:3s} {direction}')
    except: pass
" 2>/dev/null)
L3PLUS=$(grep -c '"level": "L[3-5]"' "$LEARNINGS" 2>/dev/null || echo 0)
echo "=== Research Status $(date +%H:%M) ==="
echo "Total: $TOTAL experiments | L3+: $L3PLUS"
echo "Latest:"
echo "$LAST5"
