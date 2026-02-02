# =========================
# File: ollama_backend.py
# =========================
#!/usr/bin/env python3
import json
import subprocess
import time
import urllib.request
import urllib.error


import configparser
import os
import sys

# Load config
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.txt")
config = configparser.ConfigParser()
if os.path.exists(CONFIG_FILE):
    config.read(CONFIG_FILE)
else:
    # Fallback default
    config["api"] = {
        "ollama_base_url": "http://localhost:11434"
    }

OLLAMA_BASE_URL = config["api"].get("ollama_base_url", "http://localhost:11434").strip()
OLLAMA_CHAT_URL = f"{OLLAMA_BASE_URL}/v1/chat/completions"


def _is_server_up(timeout_s: float = 0.25) -> bool:
    url = f"{OLLAMA_BASE_URL}/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=timeout_s) as resp:
            return 200 <= resp.status < 300
    except Exception:
        return False


def _start_server_cmd_window() -> None:
    """
    Windows-only behavior: start `ollama serve` in a NEW cmd window.
    When that window is closed, Ollama is terminated and models unload.
    """
    subprocess.Popen(
        ["cmd", "/c", "start", "Ollama Server", "ollama", "serve"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _wait_for_server(timeout_s: float = 12.0) -> None:
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < timeout_s:
        if _is_server_up():
            return
        time.sleep(0.15)
    raise RuntimeError("Ollama server did not become ready (http://localhost:11434)")


def _pull_if_missing(model: str) -> None:
    try:
        out = subprocess.check_output(["ollama", "list"], stderr=subprocess.DEVNULL).decode(
            "utf-8", errors="replace"
        )
    except subprocess.CalledProcessError:
        out = ""

    have = set()
    for line in out.splitlines()[1:]:
        parts = line.split()
        if parts:
            have.add(parts[0].strip())

    if model not in have:
        subprocess.run(["ollama", "pull", model], check=True)


def call_ollama_chat(prompt: str, model: str, timeout_s: float = 180.0):
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You write precise, technical git commit messages."},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_CHAT_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            result = json.loads(body)
            content = result["choices"][0]["message"]["content"].strip()
            usage = result.get("usage", {}) or {}
            return content, usage
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Ollama API HTTP error: {err}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"Ollama API connection error: {e}") from None


def generate_commit_message_local(prompt: str, model: str = "deepseek-coder:6.7b"):
    """
    Runs Ollama locally:
      - ensures model is available
      - starts server if not running (in cmd window)
      - calls OpenAI-compatible endpoint
      - stops model (optional)

    Returns: (msg, usage, started_server, timing)
    timing keys:
      - total_s
      - pull_s
      - server_start_s
      - wait_ready_s
      - inference_s
    """
    t0_total = time.perf_counter()

    # 1) Pull model if missing
    t0_pull = time.perf_counter()
    _pull_if_missing(model)
    t1_pull = time.perf_counter()

    # 2) Start server if needed
    started_server = False
    server_start_s = 0.0
    wait_ready_s = 0.0

    if not _is_server_up():
        started_server = True
        t0_srv = time.perf_counter()
        _start_server_cmd_window()
        t1_srv = time.perf_counter()
        server_start_s = t1_srv - t0_srv

        t0_wait = time.perf_counter()
        _wait_for_server(timeout_s=12.0)
        t1_wait = time.perf_counter()
        wait_ready_s = t1_wait - t0_wait

    # 3) Inference call
    t0_inf = time.perf_counter()
    msg, usage = call_ollama_chat(prompt, model=model)
    t1_inf = time.perf_counter()

    # 4) Optional: unload model
    try:
        subprocess.run(["ollama", "stop", model], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

    t1_total = time.perf_counter()

    timing = {
        "total_s": t1_total - t0_total,
        "pull_s": t1_pull - t0_pull,
        "server_start_s": server_start_s,
        "wait_ready_s": wait_ready_s,
        "inference_s": t1_inf - t0_inf,
    }

    return msg, usage, started_server, timing

