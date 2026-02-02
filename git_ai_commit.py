# =========================
# File: git_aic.py  (main script)
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


OPENAI_URL = "https://api.openai.com/v1/chat/completions"
MODEL = "gpt-5-mini"
LOCAL_MODEL = "gpt-oss:20b"
# LOCAL_MODEL = "deepseek-coder:6.7b"

# Pricing (USD per 1M tokens)
OPENAI_API_PRICING_PER_1M = {
    "gpt-5.2": {"input": 1.75, "cached_input": 0.175, "output": 14.00},
    "gpt-5.1": {"input": 1.25, "cached_input": 0.125, "output": 10.00},
    "gpt-5": {"input": 1.25, "cached_input": 0.125, "output": 10.00},
    "gpt-5-mini": {"input": 0.25, "cached_input": 0.025, "output": 2.00},
    "gpt-5-nano": {"input": 0.05, "cached_input": 0.005, "output": 0.40},
    "gpt-4.1": {"input": 2.00, "cached_input": 0.50, "output": 8.00},
    "gpt-4.1-mini": {"input": 0.40, "cached_input": 0.10, "output": 1.60},
    "gpt-4.1-nano": {"input": 0.10, "cached_input": 0.025, "output": 0.40},
    "gpt-4o": {"input": 2.50, "cached_input": 1.25, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "cached_input": 0.075, "output": 0.60},
    "gpt-realtime": {"input": 4.00, "cached_input": 0.40, "output": 16.00},
    "gpt-realtime-mini": {"input": 0.60, "cached_input": 0.06, "output": 2.40},
    "o1": {"input": 15.00, "cached_input": 7.50, "output": 60.00},
    "o3": {"input": 2.00, "cached_input": 0.50, "output": 8.00},
}

# Truncation settings (approx "pages" in terminal)
LINES_PER_PAGE = 60
MAX_DIFF_PAGES = 6
MAX_DIFF_LINES = LINES_PER_PAGE * MAX_DIFF_PAGES


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


def call_openai(api_key, prompt):
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "You write precise, technical git commit messages."},
            {"role": "user", "content": prompt},
        ],
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        OPENAI_URL,
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
        raise RuntimeError(f"OpenAI API error: {err}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"OpenAI API connection error: {e}") from None


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

    return f"""
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
{chr(10).join(files)}
{manual_block}
STAGED DIFF:
{diff}
""".strip()


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
    # - OpenAI gets truncated diff (fast, cost control)
    # - Local gets sparse digest of full diff (better signal)
    if args.local:
        diff_for_prompt = simplify_diff_for_local(diff, max_changed_lines=140)
    else:
        diff_for_prompt = diff_used

    prompt = build_prompt(files, diff_for_prompt, manual_topic=args.manual_message)

    t_ai_start = time.perf_counter()

    if args.local:
        info(f"Using local Ollama backend ({LOCAL_MODEL})")
        info("If an 'Ollama Server' window opens, close it later to unload everything.")
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
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            error("OPENAI_API_KEY not set")
            sys.exit(1)

        info(f"Using OpenAI backend ({MODEL})")
        msg, usage = call_openai(api_key, prompt)

    t_ai_end = time.perf_counter()
    info(f"Model response received in {t_ai_end - t_ai_start:.2f} s")

    # Ensure Topic line placement if manual message was provided
    msg = ensure_topic_line(msg, args.manual_message)

    print("\n========== AI-generated commit message ==========\n")
    print(msg)
    print("\n================================================\n")

    # Cost info
    if not args.local:
        est = estimate_cost_usd(MODEL, usage)
        if est:
            pt, ct, tt, cost = est
            info(f"Tokens: prompt={pt}, completion={ct}, total={tt}")
            info(f"Estimated cost: ${cost:.6f}")

    choice = input("Accept this commit message? [y/N/e]: ").strip().lower()
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

    t_end = time.perf_counter()
    info(f"Total runtime: {t_end - t_start:.2f} s")


if __name__ == "__main__":
    main()
