# Tauri UI

React + TypeScript + Vite frontend for the Semantic File System desktop app, packaged with Tauri.

## What This Folder Contains

- Vite React frontend in `src/`
- Tauri Rust shell in `src-tauri/`
- Desktop app config in `src-tauri/tauri.conf.json`

## Frontend Commands

Run all commands from this `tauri_ui/` directory.

### Install dependencies

```bash
npm install
```

### Start Vite frontend only

Starts the React dev server on `http://localhost:1420`.

```bash
npm run dev
```

### Build frontend assets

```bash
npm run build
```

### Preview the production frontend build

```bash
npm run preview
```

### Start the desktop app in development

Runs the Vite frontend and the Tauri shell together:

```bash
npm run tauri dev
```

Important behavior:

- The desktop app auto-starts the Python backend from `backend_api/app/main.py`
- On Windows it prefers `..\myenv\Scripts\python.exe` when available
- If that virtual environment is missing, it falls back to `python` from your PATH

### Build the desktop app

```bash
npm run tauri build
```

## Backend Command For UI Development

If you want to run the backend manually outside the Tauri app, run this from the repository root:

```bash
python -m uvicorn backend_api.app.main:app --host 127.0.0.1 --port 8000 --reload
```

Use that mode when you want API reloads or want to test the frontend separately with `npm run dev`.

## Recommended IDE Setup

- [VS Code](https://code.visualstudio.com/)
- [Tauri VS Code extension](https://marketplace.visualstudio.com/items?itemName=tauri-apps.tauri-vscode)
- [rust-analyzer](https://marketplace.visualstudio.com/items?itemName=rust-lang.rust-analyzer)
