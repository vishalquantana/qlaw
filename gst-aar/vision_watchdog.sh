#!/bin/bash
# Restart extract_vision.py whenever it stalls or exits; resumable via cache.
cd "$(dirname "$0")"
PY=ocr-benchmark/venv-tools/bin/python
STATUS=data/extract_vision_status.jsonl
for cycle in $(seq 1 40); do
  # target: 2888 pdfs, 1 known unprocessable -> stop at 2887 txts
  n_txt=$(ls data/text/*/*.txt 2>/dev/null | wc -l | tr -d ' ')
  if [ "$n_txt" -ge 2887 ]; then echo "WATCHDOG: complete ($n_txt txts)"; break; fi
  echo "WATCHDOG cycle $cycle: $n_txt/2887 txts, launching"
  "$PY" extract_vision.py >> vision_run.log 2>&1 &
  pid=$!
  # monitor in 60s ticks: restart if no status-line growth for 3 consecutive ticks
  stall=0
  prev=$(wc -l < "$STATUS" 2>/dev/null || echo 0)
  while kill -0 $pid 2>/dev/null; do
    sleep 60
    cur=$(wc -l < "$STATUS" 2>/dev/null || echo 0)
    if [ "$cur" -le "$prev" ]; then stall=$((stall+1)); else stall=0; fi
    prev=$cur
    if [ "$stall" -ge 3 ]; then
      echo "WATCHDOG: stalled at $cur status lines, killing cycle $cycle"
      kill -9 $pid 2>/dev/null
      pkill -9 -f "multiprocessing.spawn" 2>/dev/null
      sleep 3
      break
    fi
  done
  wait $pid 2>/dev/null
done
echo "WATCHDOG done: $(ls data/text/*/*.txt 2>/dev/null | wc -l) txts on disk"
