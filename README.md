# GitAI Commit

GitAI Commit is a command-line utility designed to automate the generation of structured, technical, and standardized git commit messages utilizing Large Language Models (LLMs). The tool provides a bridge between automated source code analysis and formal version control documentation, supporting both cloud-based and local inference backends.

## Features

- **Standardized Messaging**: Generates commit messages following the Conventional Commits specification.
- **Backend Flexibility**: Integration with OpenAI API for cloud inference and Ollama for local, privacy-preserving execution.
- **Cost Analysis**: Provides token usage metrics and cost estimation for API-based transactions.
- **Differential Analysis Optimization**: Implements intelligent diff truncation and simplification to maintain contextual relevance within model token constraints.
- **Contextual Augmentation**: Allows for the inclusion of manual topics to guide the model's focus during message generation.
- **Platform Integration**: Specific optimizations for the Windows environment, including automated management of local inference servers.

---

## Setup

### 1. Prerequisites
- Python 3.8 or higher
- **Ollama**: Required for local inference. Refer to the [Ollama Documentation](https://ollama.com/download) for installation instructions. Add to filepath
- **OpenAI API Key**: Required for remote inference. Set in envirmental vairbles.

### 2. Installation
Clone the repository to a persistent directory on your system. The implementation relies on standard Python libraries, requiring no external package installations.

### 3. Environment Configuration
For OpenAI integration, you must configure the `OPENAI_API_KEY` environmental variable.

**Windows (PowerShell):**
```powershell
$env:OPENAI_API_KEY="your_api_key_here"
# To persist this change, use:
[System.Environment]::SetEnvironmentVariable('OPENAI_API_KEY', 'your_api_key_here', 'User')
```

**Linux/macOS (Bash/Zsh):**
```bash
export OPENAI_API_KEY="your_api_key_here"
# To persist this change, add the line above to your ~/.bashrc or ~/.zshrc file.
```

### 4. Windows Convenience Script
To enable direct execution via the `gitai` command in Windows:
1. Locate `gitai_example.cmd` in the project root.
2. Rename or copy the file to `gitai.cmd`.
3. Edit `gitai.cmd` and update the file path to point to your absolute location of `git_ai_commit.py`.
   - Example: `python "C:\Users\Name\Projects\gitai\git_ai_commit.py" %*`
4. Add the directory containing `gitai.cmd` to your System PATH.

Once configured, the utility can be invoked from any repository directory simply by typing `gitai`, bypassing the need to invoke the Python interpreter manually.

## Workflow

GitAI Commit is designed to fit seamlessly into your existing Git workflow. It replaces only the manual commit message entry step.

1. **Stage Changes**: Use standard Git commands to stage your files.
   ```bash
   git add .
   # or
   git add path/to/file.py
   ```
2. **Generate Commit**: Instead of `git commit -m "..."`, invoke the utility.
   ```bash
   gitai commit
   ```
3. **Review & Approve**: The AI will analyze your staged differential and propose a message. You will be prompted to accept (`y`) or reject (`n`) the proposal before the actual commit is executed.

---

## Usage

The utility operates on currently staged changes. Ensure files are added to the git index prior to execution.

### Remote Inference (OpenAI)
```bash
gitai commit
```

### Local Inference (Ollama)
Ensure the Ollama server is accessible or installed. The utility will attempt to manage the server instance on Windows.
```bash
gitai commit --local
```

### Manual Context Injection
To provide specific thematic guidance to the model (works with both remote and local backends):
```bash
gitai commit -m "Implementation of secondary authentication logic"

# Combined with local inference
gitai commit --local -m "Fixing regression in parser"
```

*Note: The order of optional flags (`--local`, `-m`) is independent and can be used in any sequence.*

---

## Model API Configuration

Model parameters are defined within the header of `git_ai_commit.py`:
- `MODEL`: Designated OpenAI model identifier.
- `LOCAL_MODEL`: Designated Ollama model identifier (ensure you have pulled the model via `ollama pull <model_name>`).

---

## About

This project explores the application of generative models in streamlining the software development lifecycle. By reducing the cognitive overhead associated with documenting incremental code changes, GitAI Commit facilitates maintained consistency in version control history. The implementation prioritizes technical accuracy and contextual awareness through optimized preprocessing of source code differentials.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
