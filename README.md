# Semantic File System

Local-first semantic search and natural-language file operations powered by Ollama, ChromaDB, and a Python backend, with both Terminal and Tauri desktop UI workflows.

## What This Project Includes

- Python semantic runtime (SLPFS) for indexing, search, and NL command execution
- FastAPI backend service used by the desktop app
- Tauri + React frontend for file tree, chat/search, and preview UX
- Optional multimodal indexing/search pipeline (Semantixel)
- Config-driven local setup through a single config file

## Architecture

1. User submits a search or command from Terminal or UI.
2. Backend routes requests to runtime services.
3. Files are indexed to vectors using sentence-transformers.
4. ChromaDB returns semantic matches.
5. Ollama-powered LLM handles intent/command parsing and response shaping.

Primary paths:
- `slpfs/` core semantic file system runtime
- `semantixel/` multimodal services
- `backend_api/app/` FastAPI API layer and runtime management
- `tauri_ui/` desktop app frontend (React + Tauri)

## Prerequisites

Required on all OS:

- Python 3.10+ (3.11 recommended)
- Node.js 18+ and npm
- Ollama installed and available in PATH
- Git

For Tauri desktop development, install Rust toolchain:

- Rustup + stable Rust + Cargo

Install Rust toolchain:

```bash
rustup default stable
```

Install and start Ollama, then pull a model:

```bash
ollama serve
```

In another terminal:

```bash
ollama pull qwen2.5:3b
```

## OS Setup and Run Commands

### Windows (PowerShell)

```powershell
git clone https://github.com/taslim121/Semantic_file_system.git
cd Semantic_file_system

python -m venv myenv
.\myenv\Scripts\Activate.ps1

pip install --upgrade pip
pip install -r requirements.txt
pip install -r backend_api\requirements.txt
# Optional multimodal dependencies:
pip install -r requirements-multimodal-phase1.txt

cd tauri_ui
npm install
cd ..
```

Start backend API:

```powershell
.\myenv\Scripts\Activate.ps1
python -m uvicorn backend_api.app.main:app --host 127.0.0.1 --port 8000 --reload
```

Start Tauri UI (new terminal):

```powershell
cd tauri_ui
npm run tauri dev
```

Optional Terminal UI:

```powershell
.\myenv\Scripts\Activate.ps1
python terminal.py
```

### macOS (zsh/bash)

```bash
git clone https://github.com/taslim121/Semantic_file_system.git
cd Semantic_file_system

python3 -m venv myenv
source myenv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
pip install -r backend_api/requirements.txt
# Optional multimodal dependencies:
pip install -r requirements-multimodal-phase1.txt

cd tauri_ui
npm install
cd ..
```

Start backend API:

```bash
source myenv/bin/activate
python -m uvicorn backend_api.app.main:app --host 127.0.0.1 --port 8000 --reload
```

Start Tauri UI (new terminal):

```bash
cd tauri_ui
npm run tauri dev
```

Optional Terminal UI:

```bash
source myenv/bin/activate
python terminal.py
```

### Linux (Ubuntu/Debian)

System packages commonly needed for Tauri/WebKit:

```bash
sudo apt update
sudo apt install -y build-essential curl wget file libxdo-dev libssl-dev libayatana-appindicator3-dev librsvg2-dev
```

Then project setup:

```bash
git clone https://github.com/taslim121/Semantic_file_system.git
cd Semantic_file_system

python3 -m venv myenv
source myenv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
pip install -r backend_api/requirements.txt
# Optional multimodal dependencies:
pip install -r requirements-multimodal-phase1.txt

cd tauri_ui
npm install
cd ..
```

Start backend API:

```bash
source myenv/bin/activate
python -m uvicorn backend_api.app.main:app --host 127.0.0.1 --port 8000 --reload
```

Start Tauri UI (new terminal):

```bash
cd tauri_ui
npm run tauri dev
```

Optional Terminal UI:

```bash
source myenv/bin/activate
python terminal.py
```

## Configuration

Edit `config.yaml` before first use.

Current important keys:

- `directories.root_dir`: folder to index and operate on
- `directories.vector_db_dir`: local Chroma storage
- `ollama.model`: LLM model (currently `qwen2.5:3b`)
- `ollama.url`: Ollama server URL (default local)
- `embedding.model`: embedding model name
- `multimodal.enabled`: toggle multimodal indexing/search
- `multimodal.db_path`: multimodal vector DB path

Example:

```yaml
directories:
  root_dir: C:\Users\YourUser\Desktop\your_folder
  vector_db_dir: ./.lsfs_db

ollama:
  model: qwen2.5:3b
  url: http://localhost:11434

embedding:
  model: all-mpnet-base-v2

search:
  default_results: 5
  max_file_size_mb: 10

multimodal:
  enabled: true
  db_path: ./db_multimodal
```

## Running Modes

### 1) API + Desktop UI (recommended)

- Start Ollama
- Start backend API
- Start Tauri app

This mode is best for daily use.

### 2) Terminal-Only Mode

```bash
python terminal.py
```

Useful for debugging backend behavior without UI.

## API Endpoints (MVP)

Base URL:

```text
http://127.0.0.1:8000/api/v1
```

Key endpoints:

- `GET /health`
- `GET /config`
- `PUT /config`
- `PUT /config/root`
- `POST /search`
- `POST /command`
- `GET /tree`
- `POST /file/read`
- `POST /index/start`
- `GET /index/status`
- `POST /index/cancel`

## Troubleshooting

### Ollama not reachable

```text
Connection refused / model unavailable
```

Fix:

```bash
ollama serve
ollama pull qwen2.5:3b
```

### Backend import errors

Make sure virtual environment is active and dependencies are installed from both requirement files.

### Tauri build issues

- Confirm Rust is installed: `rustc --version`
- Confirm Node/npm are installed: `node -v` and `npm -v`
- On Linux, install missing system packages for WebKit/GTK

### Reset vector stores

Windows PowerShell:

```powershell
Remove-Item -Recurse -Force .lsfs_db, db_multimodal
```

macOS/Linux:

```bash
rm -rf .lsfs_db db_multimodal
```

## Recommended Ollama Models

- Balanced default: `qwen2.5:3b`
- Better quality (if resources allow): `qwen2.5:7b`
- Alternative general model: `llama3.1:8b`

Update the model in `config.yaml`, then restart backend.

## Developer Notes

- Backend API entrypoint: `backend_api/app/main.py`
- UI scripts: `tauri_ui/package.json`
- Contract and planning docs:
  - `backend-contract.md`
  - `tauri-implementation-plan.md`

## License

Use according to repository license and applicable third-party dependency licenses.
