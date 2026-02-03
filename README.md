# GitAI

GitAI is a command-line utility designed to automate the generation of structured, technical, and standardized git commit messages utilizing Large Language Models (LLMs) of your choice. The tool provides a bridge between automated source code analysis and formal version control documentation, supporting both cloud-based and local inference backends.

## Quick Start: Run

The utility integrates directly into the standard Git workflow, replacing only the manual commit message entry with an AI-augmented message by analyzing code diffs.

```bash
# 1. Stage changes using standard Git
git add .

# 2. Invoke GitAI to generate and execute the commit
gitai commit -m "Intial commit"
# or to commit without manual message: gitai commit
# or to use a local LLM model: gitai commit -m "Initial commit" --local
# or to use a remote LLM model: gitai commit -m "Initial commit" --api
# Note: Generation may take 1-3 minutes depending on the diff size and model.
# (Behavior depends on the default model set in config.txt)

# 3. Review the AI-generated commit message proposal and confirm or edit
# Input options: [y]es, [n]o, or [e]dit
# Note: If 'e' is chosen, the message will open in your default editor.
# You must SAVE and CLOSE the file to finalize the commit.

# 4. Push changes using standard Git
git push origin main
```

## Quick Start: Example AI-generated commit message

```docs: update README with Quick Start and installation guide

Lines: 35 added, 12 removed

CHANGES:
- Replaced the old project title and description with a concise overview.
- Added a “Quick Start: Run” section containing an example commit command.
- Introduced a full installation guide covering Windows, Linux, and macOS.
- Included operating‑system‑specific instructions for adding the tool to PATH and setting the api key.
- Updated the optional arguments section and removed outdated Windows‑only integration steps.

Files changed:
README.md
config.txt
```

## Quick Start: Installation

**Prerequisites**: Python 3.8+ (installed system-wide and accessible from CLI using `python` or `py`).

### Windows
1. **Download**: Clone or download this repository to a permanent location (e.g., `C:\Tools\GitAI`).
2. **Add to Path**: Add that directory to your System PATH environment variable so you can type `gitai` from anywhere.
3. **Setup API Key**: Run the following in PowerShell:
   ```powershell
   [System.Environment]::SetEnvironmentVariable('OPENAI_API_KEY', 'your-key-here', 'User')
   ```
   *(Note: Restart your terminal after updating PATH or environment variables).*

### Linux / macOS
1. **Download**: Clone this repository to your preferred location.
2. **Make Executable**:
   ```bash
   chmod +x /path/to/gitai/gitai.py
   ```
3. **Link Command**: Create a symlink to run it as `gitai`:
   ```bash
   sudo ln -s /path/to/gitai/gitai.py /usr/local/bin/gitai
   ```
4. **Setup API Key**: Add this to your `.bashrc` or `.zshrc`:
   ```bash
   export OPENAI_API_KEY="your-key-here"
   ```

---

## Core Features

- **Standardized Messaging**: Generates commit messages following the Conventional Commits specification.
- **Backend Flexibility**: Support for OpenAI API (cloud) and Ollama (local, privacy-preserving) inference.
- **Cost Analysis**: Provides token usage metrics and cost estimation for API-based transactions.
- **Differential Analysis Optimization**: Implemented intelligent diff truncation and simplification to maintain contextual relevance within token constraints.
- **Platform Integration**: Specific optimizations for the Windows environment, including automated management of local inference servers.

---

## Setup & Configuration

### 1. Prerequisites
- Python 3.8+ (installed system-wide and accessible from CLI using `python` or `py`)
- **Ollama** (Optional): Required for local inference. Refer to [Ollama.com](https://ollama.com/download).
- **API Key**: Required for remote cloud LLM inference.

### 2. Environment Configuration
Configure the `OPENAI_API_KEY` (or any name of you chosing) environmental variable for remote access.

**Windows (PowerShell):**
```powershell
[System.Environment]::SetEnvironmentVariable('OPENAI_API_KEY', 'your_api_key_here', 'User')
```

**Linux/macOS (Bash/Zsh):**
```bash
export OPENAI_API_KEY="your_api_key_here"
```

### 4. API and Model Configuration
The utility reads settings from `config.txt` located in the project directory. Ensure these values are set correctly:
- `api_url`: The endpoint for your OpenAI-compatible API (e.g., `https://api.openai.com/v1/chat/completions`).
- `api_model`: The model name to use for remote inference (e.g., `gpt-5-mini`).
- `api_key_env_name`: The name of the environment variable that stores your API key (default: `OPENAI_API_KEY`).
- `local_model`: The Ollama model for local inference.
- `ollama_base_url`: The endpoint for your local Ollama server.
- `default_backend`: Sets the default inference mode (options: `api` or `local`).
- `max_diff_lines`: Maximum number of diff lines to analyze (default: 360).
- `max_local_changed_lines`: Limit on lines analyzed for local models (default: 360).

### 5. Customizing the Prompt
The system prompt used to guide the AI can be customized by editing `prompt.txt` in the installation directory. This allows you to tailor the commit message style, structure, or rules to your team's specific needs. (Note: Ensure you preserve the `{files_list}`, `{manual_block}`, and `{diff_content}` placeholders for the tool to function correctly).

Pricing data for cost estimation is maintained in `LLM_latest_pricing.txt`.

---

## Optional Arguments

The `commit` subcommand accepts optional flags to modify the inference backend and refine the output.

### Arguments-Local Inference
Utilize a local Ollama model for inference (e.g. `deepseek-coder-v2:lite or gpt-oss:20b` or similar (note run 30b models at 4bit quantization you need around 24gb vram, smaller 1.5B model smaller can be run on smaller gpus but are less intelligent).
```bash
gitai commit --local
```

### Arguments-Remote Inference
Force the use of the remote OpenAI backend (useful if `default_backend` is set to `local`). Note the default is set to `api`.
```bash
gitai commit --api
```

### Arguments-Contextual Augmentation
Inject a manual commit message in addition to ai commit message.
```bash
gitai commit -m "Implementation of secondary authentication logic"
```

*Note: Optional flags (`--local`, `--api`, `-m`) are order-independent.*

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
