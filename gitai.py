# =========================
# File: gitai.py  (main script)
# =========================
#!/usr/bin/env python3
import os
import subprocess
import sys
import json
import urllib.request
import urllib.error
import argparse
import time

from ollama_backend import generate_commit_message_local


import configparser

# Determine script directory to locate config files
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.txt")
PRICING_FILE = os.path.join(SCRIPT_DIR, "LLM_latest_pricing.txt")
PROMPT_FILE = os.path.join(SCRIPT_DIR, "prompt.txt")

# Default Configuration
config_defaults = {
    "api_url": "https://api.openai.com/v1/chat/completions",
    "api_model": "gpt-5-mini",
    "api_key_env_name": "OPENAI_API_KEY",
    "local_model": "gpt-oss:20b",
    "default_backend": "api",
    "max_diff_lines": "360",
    "max_local_changed_lines": "180"
}

# Load Configuration File
config = configparser.ConfigParser()
if os.path.exists(CONFIG_FILE):
    config.read(CONFIG_FILE)
    if "api" in config:
        for key in config_defaults:
            if key in config["api"]:
                config_defaults[key] = config["api"][key].strip()

# Set Global Variables from Config
API_URL = config_defaults["api_url"]
API_MODEL = config_defaults["api_model"]
API_KEY_ENV_NAME = config_defaults["api_key_env_name"]
LOCAL_MODEL = config_defaults["local_model"]
DEFAULT_BACKEND = config_defaults["default_backend"].lower()
MAX_DIFF_LINES = int(config_defaults["max_diff_lines"])
MAX_LOCAL_CHANGED_LINES = int(config_defaults["max_local_changed_lines"])

# Load Pricing
OPENAI_API_PRICING_PER_1M = {}
if os.path.exists(PRICING_FILE):
    try:
        with open(PRICING_FILE, "r", encoding="utf-8") as f:
            OPENAI_API_PRICING_PER_1M = json.load(f)
    except Exception as e:
        print(f"[warn] Failed to load pricing file: {e}", file=sys.stderr)


def info(msg): print(f"[info] {msg}")
def warn(msg): print(f"[warn] {msg}")
def error(msg): print(f"[error] {msg}", file=sys.stderr)


def run(cmd):
    return subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode("utf-8", errors="replace")


def get_staged_diff():
    try:
        return run(["git", "diff", "--cached"])
    except subprocess.CalledProcessError:
        return ""


def get_staged_files():
    try:
        out = run(["git", "diff", "--cached", "--name-only"])
        return [f for f in out.splitlines() if f.strip()]
    except subprocess.CalledProcessError:
        return []


def truncate_diff(diff_text):
    lines = diff_text.splitlines()
    total = len(lines)

    if total <= MAX_DIFF_LINES:
        return diff_text, False, total, total

    kept = lines[:MAX_DIFF_LINES]
    omitted = total - MAX_DIFF_LINES
    kept.append("")
    kept.append(f"[... truncated {omitted} diff lines ...]")
    return "\n".join(kept), True, total, MAX_DIFF_LINES


def simplify_diff_for_local(diff_text, max_changed_lines=140):
    """
    Keep file headers + hunk headers + limited changed lines.
    Helps local models: clearer signal, less noise.
    """
    out = []
    changed = 0
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            out.append(line)
        elif line.startswith("index ") or line.startswith("--- ") or line.startswith("+++ "):
            out.append(line)
        elif line.startswith("@@"):
            out.append(line)
        elif (line.startswith("+") or line.startswith("-")) and not (line.startswith("+++") or line.startswith("---")):
            out.append(line)
            changed += 1
            if changed >= max_changed_lines:
                out.append("")
                out.append(f"[... truncated after {max_changed_lines} changed lines ...]")
                break
    return "\n".join(out)


def estimate_cost_usd(model, usage):
    pricing = OPENAI_API_PRICING_PER_1M.get(model)
    if not pricing:
        return None

    pt = int(usage.get("prompt_tokens", 0))
    ct = int(usage.get("completion_tokens", 0))
    tt = int(usage.get("total_tokens", pt + ct))

    cost = (pt / 1e6) * pricing["input"] + (ct / 1e6) * pricing["output"]
    return pt, ct, tt, cost


def call_api(api_key, prompt):
    payload = {
        "model": API_MODEL,
        "messages": [
            {"role": "system", "content": "You write precise, technical git commit messages."},
            {"role": "user", "content": prompt},
        ],
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            result = json.loads(body)
            return result["choices"][0]["message"]["content"].strip(), result.get("usage", {})
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API error: {err}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"API connection error: {e}") from None
    except Exception as e:
        raise RuntimeError(f"Unexpected error calling API: {e}") from None


def build_prompt(files, diff, manual_topic: str = ""):
    manual_topic = (manual_topic or "").strip()

    # If provided, the model must include it on a dedicated line right after subject.
    manual_rules = ""
    manual_block = ""
    if manual_topic:
        manual_rules = (
            "- You MUST include a one-line 'Topic:' line immediately AFTER the subject line.\n"
            "- Format exactly: Topic: <manual_topic>\n"
        )
        manual_block = f"\nManual commit message topic:\n{manual_topic}\n"

    prompt_tmpl = """
You are an expert software engineer.

Write a Conventional Commit message based on the STAGED DIFF.

Rules:
- Output ONLY the commit message (no commentary, no extra text).
- Subject line: <type>(<optional scope>): <imperative summary>, max 72 chars.
{manual_rules}- Blank line after the subject line (and after Topic line if present).
- Total number code lines added and removed.
- Blank line.
- Then write the body FIRST under heading "CHANGES:" with 2–8 concise bullet points intent articulation describing what changed and why. Format clearly with line spacing so it is easy to read.
- Then include a section titled "Files changed:" at the VERY END and include all changed files.

Files:
{files_list}
{manual_block}
STAGED DIFF:
{diff_content}
""".strip()

    if os.path.exists(PROMPT_FILE):
        try:
            with open(PROMPT_FILE, "r", encoding="utf-8") as f:
                prompt_tmpl = f.read().strip()
        except Exception as e:
            warn(f"Failed to read prompt.txt, using internal default: {e}")

    return prompt_tmpl.format(
        manual_rules=manual_rules,
        files_list="\n".join(files),
        manual_block=manual_block,
        diff_content=diff
    )


def ensure_topic_line(msg: str, manual_topic: str) -> str:
    """
    Defensive post-process:
    If manual_topic is provided but the model forgot the Topic line,
    insert it immediately after the subject line.
    """
    manual_topic = (manual_topic or "").strip()
    if not manual_topic:
        return msg.strip()

    lines = msg.splitlines()
    if not lines:
        return msg.strip()

    # Find first non-empty line as subject
    subject_idx = None
    for i, ln in enumerate(lines):
        if ln.strip():
            subject_idx = i
            break
    if subject_idx is None:
        return msg.strip()

    # Check if Topic already exists in the next few lines (before first blank)
    j = subject_idx + 1
    while j < len(lines) and lines[j].strip():
        if lines[j].strip().lower().startswith("topic:"):
            return msg.strip()
        j += 1

    # Insert Topic line right after subject
    new_lines = lines[:subject_idx + 1] + [f"Topic: {manual_topic}"] + lines[subject_idx + 1:]
    return "\n".join(new_lines).strip()


def main():
    t_start = time.perf_counter()

    parser = argparse.ArgumentParser(prog="gitai")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # 'commit' subcommand
    commit_parser = subparsers.add_parser("commit", help="Generate and execute an AI-assisted commit")
    commit_parser.add_argument(
        "--local",
        action="store_true",
        help="Use local Ollama backend"
    )
    commit_parser.add_argument(
        "--api",
        action="store_true",
        help="Use remote API backend"
    )
    commit_parser.add_argument(
        "-m",
        "--message",
        dest="manual_message",
        default="",
        help="Optional manual commit message topic"
    )

    args = parser.parse_args()

    if args.command != "commit":
        parser.print_help()
        sys.exit(0)

    # Determine backend: explicit flag takes precedence, else use config default
    use_local = False
    if args.local:
        use_local = True
    elif args.api:
        use_local = False
    else:
        use_local = (DEFAULT_BACKEND == "local")

    diff = get_staged_diff()
    files = get_staged_files()

    if not diff.strip():
        error("No staged changes. Run: git add <files>")
        sys.exit(1)

    diff_used, truncated, total, kept = truncate_diff(diff)
    if truncated:
        warn(f"Large diff: {total} lines, using first {kept}")
    else:
        info(f"Staged diff size: {total} lines")

    # One prompt for both backends:
    # - API gets truncated diff (fast, cost control)
    # - Local gets sparse digest of full diff (better signal)
    if use_local:
        diff_for_prompt = simplify_diff_for_local(diff, max_changed_lines=MAX_LOCAL_CHANGED_LINES)
    else:
        diff_for_prompt = diff_used

    prompt = build_prompt(files, diff_for_prompt, manual_topic=args.manual_message)

    t_ai_start = time.perf_counter()
    info("Generating commit message... Please be patient, this may take 1-3 minutes depending on context length.")

    if use_local:
        info(f"Using local Ollama backend ({LOCAL_MODEL})")
        msg, usage, started, timing = generate_commit_message_local(prompt, model=LOCAL_MODEL)
        if started:
            info("Ollama server started in a separate cmd window")

        info(
            "Local timing (s): "
            f"pull={timing.get('pull_s', 0.0):.2f}, "
            f"server_start={timing.get('server_start_s', 0.0):.2f}, "
            f"wait_ready={timing.get('wait_ready_s', 0.0):.2f}, "
            f"inference={timing.get('inference_s', 0.0):.2f}, "
            f"total_local={timing.get('total_s', 0.0):.2f}"
        )
    else:
        # Check configured env var
        api_key = os.getenv(API_KEY_ENV_NAME)
        if not api_key:
            error(f"Environment variable '{API_KEY_ENV_NAME}' not set. Please set it or change 'api_key_env_name' in config.txt")
            sys.exit(1)

        info(f"Using remote API backend ({API_MODEL})")
        msg, usage = call_api(api_key, prompt)

    t_ai_end = time.perf_counter()

    # Ensure Topic line placement if manual message was provided
    msg = ensure_topic_line(msg, args.manual_message)

    print("\n========== AI-generated commit message ==========\n")
    print(msg)
    print("\n================================================\n")
    info(f"LLM Inference time: {t_ai_end - t_ai_start:.2f} s")

    # Cost info
    if not use_local:
        est = estimate_cost_usd(API_MODEL, usage)
        if est:
            pt, ct, tt, cost = est
            info(f"Tokens: prompt={pt}, completion={ct}, total={tt}")
            info(f"Estimated cost: ${cost:.6f}")

    choice = input("Accept this commit message? [y]es/[n]o/[e]dit: ").strip().lower()
    if choice in ("y", "e"):
        lines = msg.splitlines()

        # Subject = first non-empty line
        subject = ""
        subject_idx = None
        for i, ln in enumerate(lines):
            if ln.strip():
                subject = ln
                subject_idx = i
                break

        if not subject.strip():
            error("Empty commit subject from model output")
            sys.exit(1)

        # Body is everything after the subject line, skipping exactly one blank line if present
        body_lines = lines[subject_idx + 1:] if subject_idx is not None else []
        # If the next line is blank, drop it so `-m subject -m body` doesn't start with a blank line
        if body_lines and not body_lines[0].strip():
            body_lines = body_lines[1:]
        body = "\n".join(body_lines).rstrip()

        cmd = ["git", "commit", "-m", subject]
        if body.strip():
            cmd += ["-m", body]

        env = os.environ.copy()
        if choice == "e":
            cmd.append("--edit")
            cmd.append("--cleanup=strip")
            # Force Notepad on Windows for a familiar GUI editing experience
            if os.name == "nt":
                env["GIT_EDITOR"] = "notepad"

        res = subprocess.run(cmd, env=env)
        if res.returncode != 0:
            error(f"git commit failed with code {res.returncode}")
            sys.exit(res.returncode)

        info("Commit created")
    else:
        warn("Commit aborted")




if __name__ == "__main__":
    main()
