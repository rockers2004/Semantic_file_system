# Tauri Implementation Plan (Python Backend + Local APIs)

## Goal
Ship a Windows-first desktop app with Tauri UI and Python backend in 2 weeks, while keeping architecture ready for long-term expansion.

## Scope (MVP)
1. Root folder selection
2. File tree navigation
3. File preview (read)
4. Semantic search with ranked results
5. Natural language command input
6. Health checks (backend, Ollama, model)
7. Indexing start/status/cancel
8. Windows packaging

## Out of Scope (for 2-week MVP)
1. Linux/macOS installers
2. Advanced deep research UX
3. Plugin system
4. Mandatory Docker runtime
5. Auto-update pipeline

## Target Architecture
1. Tauri app (frontend shell + web UI)
2. Python API service (local only)
3. Existing core modules reused under service layer
4. API communication via HTTP on 127.0.0.1
5. Tauri starts Python backend as sidecar and waits for health readiness

## Backend API Layers
1. Router layer: request/response validation
2. Service layer: calls existing backend logic
3. Job manager: progress-aware long tasks
4. Error mapper: stable error codes for UI

## API Design Rules
1. Prefix all endpoints with /api/v1
2. JSON-only payloads
3. Shared response envelope
4. Stable error codes
5. Long operations return job_id and status endpoints
6. Strict path validation (no traversal outside configured root)

## Proposed Endpoints

### Health and Config
1. GET /api/v1/health
2. GET /api/v1/config
3. PUT /api/v1/config

### File Tree and File Ops
1. GET /api/v1/tree?path=<optional>&depth=1
2. POST /api/v1/file/read
3. POST /api/v1/file/write
4. POST /api/v1/file/move
5. POST /api/v1/file/delete

### Search and Commands
1. POST /api/v1/search
2. POST /api/v1/command
3. GET /api/v1/search/stats

### Indexing Jobs
1. POST /api/v1/index/start
2. GET /api/v1/index/status?job_id=...
3. POST /api/v1/index/cancel

## Response Contract

### Success envelope
{
  "ok": true,
  "data": {},
  "error": null,
  "meta": {
    "request_id": "uuid"
  }
}

### Error envelope
{
  "ok": false,
  "data": null,
  "error": {
    "code": "OLLAMA_UNAVAILABLE",
    "message": "Ollama is not reachable",
    "details": {}
  },
  "meta": {
    "request_id": "uuid"
  }
}

## Security Baseline
1. Bind backend to 127.0.0.1 only
2. Per-session auth token passed from Tauri to backend
3. Require token header for all endpoints
4. Validate and normalize all paths

## Packaging Strategy
1. Package Python backend as sidecar executable
2. Bundle sidecar in Tauri app
3. Installer checks Ollama and required model
4. Windows first, then expand to Linux/macOS

## 14-Day Implementation Plan
1. Day 1: Scaffold Tauri app and backend skeleton, add health endpoint
2. Day 2: Add config endpoints and startup validations
3. Day 3: Implement tree endpoint and render file tree in UI
4. Day 4: Implement read endpoint and file preview panel
5. Day 5: Implement search endpoint and search UI flow
6. Day 6: Implement command endpoint and command panel
7. Day 7: Implement index start/status/cancel backend
8. Day 8: Wire indexing progress UI and cancel action
9. Day 9: Add global error mapping and frontend error handling
10. Day 10: Integrate Tauri sidecar startup/shutdown lifecycle
11. Day 11: Add session token auth and path hardening
12. Day 12: Build first packaged app with sidecar
13. Day 13: Clean machine test and Ollama setup flow
14. Day 14: Bug fixes and release candidate

## Definition of Done
1. App launches and starts backend automatically
2. Health check is visible and actionable
3. File tree and preview work
4. Search returns ranked results
5. Command panel executes requests reliably
6. Indexing progress and cancel are functional
7. Installer works on a clean Windows machine

## Immediate Next Actions
1. Finalize endpoint list in backend-contract.md
2. Scaffold backend API project with /api/v1/health first
3. Scaffold Tauri UI and health polling screen
4. Verify sidecar start and graceful shutdown
