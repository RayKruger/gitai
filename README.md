# GitAI Commit

GitAI Commit is a command-line utility designed to automate the generation of structured, technical, and standardized git commit messages utilizing Large Language Models (LLMs). The tool provides a bridge between automated source code analysis and formal version control documentation, supporting both cloud-based and local inference backends.

## Quick Start

The utility integrates directly into the standard Git cycle, replacing only the manual message entry phase.

```bash
# 1. Stage changes using standard Git
git add .

# 2. Invoke GitAI to generate and execute the commit
gitai commit -m "Integration of core logic"

# 3. Review the AI-generated proposal and confirm (y/n/e)

# 4. Push changes using standard Git
git push
```

---

## Features

- **Standardized Messaging**: Generates commit messages following the Conventional Commits specification.
- **Backend Flexibility**: Support for OpenAI API (cloud) and Ollama (local, privacy-preserving) inference.
- **Cost Analysis**: Provides token usage metrics and cost estimation for API-based transactions.
- **Differential Analysis Optimization**: Implemented intelligent diff truncation and simplification to maintain contextual relevance within token constraints.
- **Platform Integration**: Specific optimizations for the Windows environment, including automated management of local inference servers.

---

## Setup & Configuration

### 1. Prerequisites
- Python 3.8+
- **Ollama** (Optional): Required for local inference. Refer to [Ollama.com](https://ollama.com/download).
- **API Key**: Required for OpenAI inference.

### 2. Environment Configuration
Configure the `OPENAI_API_KEY` environmental variable for cloud access.

**Windows (PowerShell):**
```powershell
[System.Environment]::SetEnvironmentVariable('OPENAI_API_KEY', 'your_api_key_here', 'User')
```

**Linux/macOS (Bash/Zsh):**
```bash
export OPENAI_API_KEY="your_api_key_here"
```

### 3. Windows Integration
To enable the `gitai` command locally:
1. Rename `gitai_example.cmd` to `gitai.cmd`.
2. Update the script path inside `gitai.cmd` to point to the absolute location of `git_ai_commit.py`.
3. Add the project directory to your System PATH.

---

## Advanced Usage

The `commit` subcommand accepts optional flags to modify the inference backend and refine the output.

### Local Inference
Utilize a local Ollama model for inference (standard: `deepseek-coder` or similar).
```bash
gitai commit --local
```

### Contextual Augmentation
Inject a manual topic or context that the AI will incorporate into the structured message.
```bash
gitai commit -m "Implementation of secondary authentication logic"
```

*Note: Optional flags (`--local`, `-m`) are order-independent.*

---

## Technical Details

Model parameters are defined within the header of `git_ai_commit.py`:
- `MODEL`: Designated OpenAI model identifier.
- `LOCAL_MODEL`: Designated Ollama model identifier.

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
