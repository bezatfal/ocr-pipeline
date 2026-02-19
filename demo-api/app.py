import os
import re
import json
import time
import uuid
import shutil
import sqlite3
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List

import requests
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ---- Config ----
REPO_ROOT = Path(__file__).resolve().parents[1]  # /mnt/ai/work/ocr-pipeline
JOBS_DIR = REPO_ROOT / "jobs"
JOBS_DIR.mkdir(parents=True, exist_ok=True)

VLLM_BASE = os.environ.get("VLLM_BASE", "http://127.0.0.1:8000")
VLLM_CHAT_URL = f"{VLLM_BASE}/v1/chat/completions"
DEFAULT_MODEL = os.environ.get("VLLM_MODEL", "Qwen/Qwen2.5-7B-Instruct")

# Choose which pipeline runner you want to call for the demo.
# Start with tiles (usually more robust on big PDFs), but you can switch to run_pipeline.sh.
PIPELINE_SCRIPT = os.environ.get("PIPELINE_SCRIPT", str(REPO_ROOT / "run_pipeline_tiles.sh"))

# If your pipeline outputs known files, we’ll look for them here. You can adjust later.
RESULT_TEXT_CANDIDATES = [
    "output.txt",
    "extracted.txt",
    "merged.txt",
    "doctr.txt",
    "result.txt",
]

app = FastAPI(title="OCR + vLLM Demo API", version="0.1")

# For localhost demo, CORS is fine wide-open.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Models ----
class RunRequest(BaseModel):
    # If you have different modes, you can add switches here.
    mode: str = "default"

class ChatRequest(BaseModel):
    message: str
    max_tokens: int = 256
    temperature: float = 0.0
    use_context: bool = True  # include extracted text as context (truncated)

class SearchResponse(BaseModel):
    query: str
    results: List[Dict[str, Any]]

# ---- Helpers ----
def job_paths(job_id: str) -> Dict[str, Path]:
    base = JOBS_DIR / job_id
    return {
        "base": base,
        "input": base / "input",
        "output": base / "output",
        "log": base / "run.log",
        "meta": base / "meta.json",
    }

def safe_job_id() -> str:
    return uuid.uuid4().hex[:12]

def read_tail(path: Path, max_bytes: int = 64_000) -> str:
    if not path.exists():
        return ""
    data = path.read_bytes()
    if len(data) <= max_bytes:
        return data.decode("utf-8", errors="replace")
    return data[-max_bytes:].decode("utf-8", errors="replace")

def write_meta(paths: Dict[str, Path], patch: Dict[str, Any]) -> None:
    meta = {}
    if paths["meta"].exists():
        try:
            meta = json.loads(paths["meta"].read_text(encoding="utf-8"))
        except Exception:
            meta = {}
    meta.update(patch)
    paths["meta"].write_text(json.dumps(meta, indent=2), encoding="utf-8")

def load_meta(paths: Dict[str, Path]) -> Dict[str, Any]:
    if not paths["meta"].exists():
        return {}
    try:
        return json.loads(paths["meta"].read_text(encoding="utf-8"))
    except Exception:
        return {}

def find_extracted_text(paths: Dict[str, Path]) -> Optional[Path]:
    # Look for a text result file in output dir
    out_dir = paths["output"]
    if not out_dir.exists():
        return None
    # 1) Try known filenames
    for name in RESULT_TEXT_CANDIDATES:
        p = out_dir / name
        if p.exists() and p.is_file():
            return p
    # 2) Otherwise first .txt by size
    txts = sorted(out_dir.glob("*.txt"), key=lambda p: p.stat().st_size if p.exists() else 0, reverse=True)
    return txts[0] if txts else None

def truncate_for_context(text: str, max_chars: int = 12_000) -> str:
    # Keep head+tail so the model sees both beginning and end.
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    return text[:half] + "\n\n...[truncated]...\n\n" + text[-half:]

def vllm_chat(messages: List[Dict[str, str]], max_tokens: int, temperature: float) -> Dict[str, Any]:
    payload = {
        "model": DEFAULT_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    r = requests.post(VLLM_CHAT_URL, json=payload, timeout=120)
    r.raise_for_status()
    return r.json()

# ---- API ----
@app.get("/health")
def health():
    # quick vLLM ping
    try:
        m = requests.get(f"{VLLM_BASE}/v1/models", timeout=3).json()
        ok = True
    except Exception:
        m = None
        ok = False
    return {"ok": True, "vllm_reachable": ok, "vllm_models": m}

@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    job_id = safe_job_id()
    paths = job_paths(job_id)
    paths["input"].mkdir(parents=True, exist_ok=True)
    paths["output"].mkdir(parents=True, exist_ok=True)

    # Save upload
    in_path = paths["input"] / file.filename
    with in_path.open("wb") as f:
        content = await file.read()
        f.write(content)

    write_meta(paths, {
        "job_id": job_id,
        "filename": file.filename,
        "created_at": time.time(),
        "status": "uploaded",
    })

    return {"job_id": job_id, "filename": file.filename}

@app.post("/api/run/{job_id}")
def run_job(job_id: str, req: RunRequest):
    paths = job_paths(job_id)
    meta = load_meta(paths)
    if not paths["input"].exists():
        raise HTTPException(status_code=404, detail="Job not found")

    # Prevent double-run (simple guard)
    status = meta.get("status", "")
    if status in ("running",):
        return {"job_id": job_id, "status": "running"}

    # Determine input file (first file in input dir)
    inputs = list(paths["input"].glob("*"))
    if not inputs:
        raise HTTPException(status_code=400, detail="No input file for this job")
    in_file = inputs[0]

    # Log file
    paths["log"].parent.mkdir(parents=True, exist_ok=True)
    paths["log"].write_text("", encoding="utf-8")

    # Mark running
    write_meta(paths, {"status": "running", "started_at": time.time(), "mode": req.mode})

    # Build command
    # NOTE: This assumes your run_pipeline_tiles.sh accepts input and output directories.
    # If your script signature differs, adjust here.
    cmd = [
        "bash",
        str(PIPELINE_SCRIPT),
        str(in_file),
        str(paths["output"]),
    ]

    # Start subprocess detached; store PID
    with paths["log"].open("ab") as logf:
        p = subprocess.Popen(
            cmd,
            cwd=str(REPO_ROOT),
            stdout=logf,
            stderr=subprocess.STDOUT,
            env=os.environ.copy(),
        )

    write_meta(paths, {"pid": p.pid})

    return {"job_id": job_id, "status": "running", "pid": p.pid, "cmd": cmd}

@app.get("/api/status/{job_id}")
def status(job_id: str):
    paths = job_paths(job_id)
    meta = load_meta(paths)
    if not paths["base"].exists():
        raise HTTPException(status_code=404, detail="Job not found")

    pid = meta.get("pid")
    running = False
    exit_code = meta.get("exit_code")
    if pid:
        # check if process exists
        try:
            os.kill(int(pid), 0)
            running = True
        except Exception:
            running = False

    # If it was running but no longer exists and we don't have exit_code, set completed best-effort.
    if meta.get("status") == "running" and not running and exit_code is None:
        # We don't have a reliable exit code without a process manager; mark "completed" if we see output.
        extracted = find_extracted_text(paths)
        new_status = "completed" if extracted else "finished"
        write_meta(paths, {"status": new_status, "finished_at": time.time()})
        meta = load_meta(paths)

    return {
        "job_id": job_id,
        "meta": meta,
        "running": running,
        "log_tail": read_tail(paths["log"]),
    }

@app.get("/api/result/{job_id}")
def result(job_id: str):
    paths = job_paths(job_id)
    if not paths["base"].exists():
        raise HTTPException(status_code=404, detail="Job not found")

    extracted = find_extracted_text(paths)
    if not extracted:
        return {"job_id": job_id, "has_result": False, "text": ""}

    text = extracted.read_text(encoding="utf-8", errors="replace")
    return {"job_id": job_id, "has_result": True, "file": str(extracted.name), "text": text}

@app.get("/api/download/{job_id}")
def download(job_id: str):
    paths = job_paths(job_id)
    if not paths["base"].exists():
        raise HTTPException(status_code=404, detail="Job not found")

    # Zip the job folder
    zip_path = paths["base"].with_suffix(".zip")
    if zip_path.exists():
        zip_path.unlink()
    shutil.make_archive(str(paths["base"]), "zip", str(paths["base"]))
    return FileResponse(str(zip_path), filename=f"{job_id}.zip")

@app.post("/api/chat/{job_id}")
def chat(job_id: str, req: ChatRequest):
    paths = job_paths(job_id)
    if not paths["base"].exists():
        raise HTTPException(status_code=404, detail="Job not found")

    context = ""
    if req.use_context:
        extracted = find_extracted_text(paths)
        if extracted and extracted.exists():
            context = truncate_for_context(extracted.read_text(encoding="utf-8", errors="replace"))

    messages = []
    if context:
        messages.append({
            "role": "system",
            "content": "You are a helpful assistant. Use the provided extracted text as the primary source of truth. If the answer is not in the text, say so."
        })
        messages.append({
            "role": "user",
            "content": f"Extracted text:\n\n{context}\n\nQuestion: {req.message}"
        })
    else:
        messages.append({"role": "user", "content": req.message})

    try:
        out = vllm_chat(messages, max_tokens=req.max_tokens, temperature=req.temperature)
        answer = out["choices"][0]["message"]["content"]
        usage = out.get("usage", {})
        return {"job_id": job_id, "answer": answer, "usage": usage}
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"vLLM call failed: {e}")

@app.get("/api/search/{job_id}")
def search(job_id: str, q: str):
    """
    Minimal search: naive substring search across extracted text.
    (We can wire your sqlite index next, but this is demo-friendly + reliable.)
    """
    paths = job_paths(job_id)
    if not paths["base"].exists():
        raise HTTPException(status_code=404, detail="Job not found")
    extracted = find_extracted_text(paths)
    if not extracted:
        return {"query": q, "results": []}

    text = extracted.read_text(encoding="utf-8", errors="replace")
    pattern = re.compile(re.escape(q), re.IGNORECASE)
    results = []
    for m in pattern.finditer(text):
        start = max(0, m.start() - 80)
        end = min(len(text), m.end() + 80)
        snippet = text[start:end].replace("\n", " ")
        results.append({"pos": m.start(), "snippet": snippet})
        if len(results) >= 20:
            break

    return {"query": q, "results": results}
