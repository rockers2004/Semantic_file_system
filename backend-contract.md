# Backend Integration Contract

Version: 1.0.0
Status: Locked for GUI MVP
Scope: LocalSLPFS callable surface and dependent LLM/vector behavior for desktop UI integration

## 1. Purpose
This document freezes the backend integration points the GUI can call during the MVP sprint.
Any breaking change requires a contract version bump.

## 2. Canonical Entry Point
- Class: LocalSLPFS
- File: slpfs/file_system.py
- Initialization dependency: SLPFSConfig

## 3. Allowed GUI Calls (Public Contract)
Only these methods are allowed for direct GUI integration through an adapter/service layer.

1. create_file(file_name: str, content: str = "") -> dict
2. create_directory(dir_name: str) -> dict
3. write_file(file_name: str, content: str, append: bool = False) -> dict
4. read_file(file_name: str) -> dict
5. search_files(query: str, k: int = 5, keywords: str | None = None) -> dict
6. list_files(subdir: str = "") -> dict
7. delete_file(file_name: str) -> dict
8. move_file(source: str, destination: str) -> dict
9. copy_file(source: str, destination: str) -> dict
10. reindex_all() -> dict
11. get_stats() -> dict
12. process_natural_language(user_input: str) -> dict

Non-contract/private behavior:
- _execute_operation(...) is internal routing, not directly called by GUI.

## 4. Standard Response Shape
All operation responses must follow one of these patterns.

Success shape:
- success: true
- operation-specific fields (message, results, content, stats, etc.)

Error shape:
- success: false
- error: string

UI integration rule:
- UI must branch only on success boolean and show error text when success is false.

## 5. Natural Language Operation Contract
The LLM parser is expected to return:
- operation: string
- parameters: object
- confidence: float

Supported operation values:
- create_file
- create_dir
- write
- read
- search
- list
- delete
- move
- copy
- reindex
- stats

Routing notes:
- process_natural_language returns success false for parse/connection errors.
- If confidence < 0.5, backend returns user-facing understanding error.

## 6. Vector Store Contract Dependencies
The following behaviors are relied upon by file_system.py:

1. index_file(...) returns one of: indexed, unchanged, error
2. index_directory(...) returns stats object:
   - indexed: int
   - unchanged: int
   - errors: int
3. search(...) returns list of objects with:
   - file_path
   - file_name
   - relative_path
   - preview
   - score
4. remove_file(...) returns bool
5. get_stats(...) returns at least:
   - total_files
   - collection_name

## 7. Ollama Handler Contract Dependencies
The following LLM behavior is part of integration assumptions:

1. _test_connection checks service reachability
2. parse_command(...) returns structured object with operation/parameters/confidence or operation=error
3. summarize_results(...) returns short string and must not break core operation flow if unavailable

## 8. Runtime Configuration Contract
Runtime values are sourced from config loader and/or defaults from config class.
GUI must not hardcode model, URL, or root path.

Required runtime keys:
- root_dir
- vector_db_dir
- ollama_model
- ollama_url
- embedding_model
- default_search_results
- max_file_size_mb
- enable_caching
- enable_versioning
- enable_redis

## 9. Change Control
Breaking change examples:
- Renaming any method in Section 3
- Removing success/error response fields
- Renaming NL operation tokens
- Changing vector search result fields

When breaking change is needed:
1. Bump contract version
2. Update GUI adapter mappings
3. Re-run integration smoke tests

## 10. MVP Integration Rules
1. GUI calls backend only through one adapter module.
2. No direct calls from widgets into vector store or llm handler.
3. Long-running operations must execute in worker threads.
4. Exceptions are converted into error responses before reaching UI.
