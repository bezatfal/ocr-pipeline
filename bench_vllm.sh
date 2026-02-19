#!/usr/bin/env bash
set -euo pipefail

MODEL="${MODEL:-Qwen/Qwen2.5-7B-Instruct}"
PROMPT="${PROMPT:-Summarize the key technical steps to build a secure document processing pipeline. Use 8 bullets.}"

J="${1:-16}"     # concurrency
N="${2:-100}"    # total requests

REQ="$(jq -cn --arg m "$MODEL" --arg p "$PROMPT" '{
  model: $m,
  messages: [{role:"user", content:$p}],
  max_tokens: 200,
  temperature: 0
}')"
export REQ

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

job='
t0=$(date +%s.%N)
resp=$(curl -sS --max-time 60 http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d "$REQ")
tok=$(jq -r ".usage.completion_tokens // 0" <<<"$resp")
t1=$(date +%s.%N)
T0="$t0" T1="$t1" TOK="$tok" python3 -c "import os,decimal; t0=os.environ[\"T0\"]; t1=os.environ[\"T1\"]; tok=os.environ[\"TOK\"]; lat=float(decimal.Decimal(t1)-decimal.Decimal(t0)); print(f\"{lat} {tok}\")"
'

run_start=$(date +%s.%N)

parallel -j "$J" --lb --env REQ --halt now,fail=1 \
  "bash -lc '$job'" ::: $(seq 1 "$N") > "$tmp"

run_end=$(date +%s.%N)

python3 - "$tmp" "$run_start" "$run_end" "$J" "$N" <<'PY'
import sys, numpy as np, decimal

path, run_start, run_end, J, N = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
run_s = float(decimal.Decimal(run_end) - decimal.Decimal(run_start))

lats, toks = [], []
with open(path, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        a, b = line.split()
        lats.append(float(a))
        toks.append(int(b))

lats = np.array(lats, dtype=float)
toks = np.array(toks, dtype=int)

pct = lambda p: float(np.percentile(lats, p))
total_toks = int(toks.sum())

print(f"model_concurrency={J} requests={len(lats)}/{N}")
print(f"latency_s: mean={lats.mean():.3f} p50={pct(50):.3f} p95={pct(95):.3f} p99={pct(99):.3f} max={lats.max():.3f}")
print(f"completion_tokens: total={total_toks} mean={toks.mean():.1f} min={toks.min()} max={toks.max()}")
print(f"wall_time_s: {run_s:.3f}")
print(f"throughput_req_s: {len(lats)/run_s:.3f}")
print(f"throughput_tok_s: {total_toks/run_s:.1f}")
PY
