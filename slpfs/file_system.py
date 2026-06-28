"""
slpfs/file_system.py

Handles semantic indexing, searching, standard file operations, stats/reindexing, and natural language command routing through as LLM

Responsibilities:
- Mounting and indexing the root directory on initialization.
- Create, read, write, delete, move, and copy files/directories with automatic vector store updates.
- Semantic search using the vector store with optional keyword filtering.
- Re-indexing all files and providing system statistics.
- Processing natural language commands by parsing them with the LLM and executing the corresponding file operations.

required components:
- config: SLPFSConfig instance for settings
- vector_store: VectorStore instance for embedding and searching file content
- llm: OllamaHandler instance for parsing commands and summarizing results

version: 1.0.0
"""

import os
import shutil
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from slpfs.vector_store import VectorStore
from slpfs.llm_handler import OllamaHandler
from slpfs.config import  SLPFSConfig

logger = logging.getLogger(__name__)

class LocalSLPFS:
    """Local LLM-based Semantic File System"""
    
    def __init__(self, config: SLPFSConfig):
        self.config = config
        self.root_dir = config.root_dir
        
        logger.info("Initializing Local SLPFS")
        
        # Initialize components
        self.vector_store = VectorStore(
            config.vector_db_dir,
            config.embedding_model,
            config.max_file_size_mb,
        )
        
        self.llm = OllamaHandler(
            config.ollama_model,
            config.ollama_url
        )
        
        # Mount root directory
        self._mount_root()
        
        logger.info("SLPFS Ready")
    
    def _mount_root(self):
        """Mount and index root directory"""
        logger.info("Mounting root directory: %s", self.root_dir)
        
        if os.path.exists(self.root_dir):
            # Re-index existing files
            stats = self. vector_store.index_directory(self.root_dir)
            logger.info("Mounted with %s files indexed", stats["indexed"])
        else:
            os.makedirs(self.root_dir, exist_ok=True)
            logger.info("Created new root directory")
    
    def create_file(self, file_name: str, content: str = "") -> Dict[str, Any]:
        """Create a new file"""
        try:
            file_path = os.path.join(self.root_dir, file_name)
            
            # Create parent directories if needed
            os.makedirs(os.path.dirname(file_path) if os.path.dirname(file_name) else self.root_dir, exist_ok=True)
            
            # Create file
            with open(file_path, 'w') as f:
                f.write(content)
            
            # Index file if it has content
            if content. strip():
                self.vector_store.index_file(file_path, self.root_dir)
            
            return {
                "success":  True,
                "file_path": file_path,
                "relative_path": file_name,
                "message": f"Created file: {file_name}"
            }
        
        except Exception as e:
            logger.error("Error creating file: %s", e)
            return {"success": False, "error": str(e)}
    
    def create_directory(self, dir_name: str) -> Dict[str, Any]:
        """Create a directory"""
        try:
            dir_path = os.path.join(self.root_dir, dir_name)
            os.makedirs(dir_path, exist_ok=True)
            
            return {
                "success":  True,
                "dir_path": dir_path,
                "message": f"Created directory: {dir_name}"
            }
        
        except Exception as e: 
            logger.error("Error creating directory: %s", e)
            return {"success": False, "error": str(e)}
    
    def write_file(self, file_name: str, content: str, append: bool = False) -> Dict[str, Any]:
        """Write content to file"""
        try: 
            file_path = os.path.join(self.root_dir, file_name)
            
            # Create file if it doesn't exist
            if not os.path.exists(file_path):
                os.makedirs(os.path. dirname(file_path) if os.path.dirname(file_name) else self.root_dir, exist_ok=True)
            
            mode = 'a' if append else 'w'
            with open(file_path, mode) as f:
                f.write(content)
            
            # Re-index file
            self.vector_store.index_file(file_path, self.root_dir)
            
            return {
                "success": True,
                "file_path": file_path,
                "message": f"{'Appended to' if append else 'Written to'}:  {file_name}"
            }
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def read_file(self, file_name: str) -> Dict[str, Any]:
        """Read file content"""
        try: 
            file_path = os. path.join(self.root_dir, file_name)
            
            if not os.path. exists(file_path):
                return {"success": False, "error": f"File not found: {file_name}"}
            
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            return {
                "success": True,
                "file_name": file_name,
                "content": content,
                "size": len(content)
            }
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def search_files(self, query: str, k: int = 5, keywords: Optional[str] = None) -> Dict[str, Any]:
        """Semantic search for files"""
        results = self.vector_store.search(query, k, keywords)
        
        return {
            "success": True,
            "query": query,
            "results": results,
            "count": len(results)
        }
    
    def list_files(self, subdir: str = "") -> Dict[str, Any]:
        """List files in directory"""
        try: 
            target_dir = os.path.join(self.root_dir, subdir) if subdir else self.root_dir
            
            if not os.path.exists(target_dir):
                return {"success": False, "error": f"Directory not found: {subdir}"}
            
            files = []
            dirs = []
            
            for item in os.listdir(target_dir):
                if item.startswith('.'):
                    continue
                
                item_path = os.path.join(target_dir, item)
                if os.path.isfile(item_path):
                    files.append({
                        "name": item,
                        "size": os. path.getsize(item_path),
                        "modified": datetime.fromtimestamp(os. path.getmtime(item_path)).isoformat()
                    })
                elif os.path.isdir(item_path):
                    dirs.append(item)
            
            return {
                "success": True,
                "path": subdir or "/",
                "directories": dirs,
                "files":  files,
                "total": len(files) + len(dirs)
            }
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def delete_file(self, file_name: str) -> Dict[str, Any]:
        """Delete a file or directory"""
        try:
            file_path = os.path. join(self.root_dir, file_name)
            
            if not os.path.exists(file_path):
                return {"success":  False, "error": f"Not found: {file_name}"}
            
            if os.path.isfile(file_path):
                os.remove(file_path)
                self.vector_store.remove_file(file_path)
                return {"success": True, "message": f"Deleted file: {file_name}"}
            elif os.path.isdir(file_path):
                shutil. rmtree(file_path)
                return {"success": True, "message":  f"Deleted directory: {file_name}"}
            else:
                return {"success": False, "error": "Unknown file type"}
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def move_file(self, source: str, destination: str) -> Dict[str, Any]:
        """Move or rename a file"""
        try: 
            source_path = os.path.join(self.root_dir, source)
            dest_path = os.path.join(self.root_dir, destination)
            
            if not os.path.exists(source_path):
                return {"success": False, "error": f"Source not found: {source}"}
            
            # Create destination directory if needed
            os.makedirs(os.path.dirname(dest_path) if os.path.dirname(destination) else self.root_dir, exist_ok=True)
            
            shutil.move(source_path, dest_path)
            
            # Re-index if it's a file
            if os.path.isfile(dest_path):
                self.vector_store. remove_file(source_path)
                self.vector_store.index_file(dest_path, self.root_dir)
            
            return {
                "success": True,
                "message": f"Moved {source} to {destination}"
            }
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def copy_file(self, source:  str, destination: str) -> Dict[str, Any]:
        """Copy a file"""
        try: 
            source_path = os. path.join(self.root_dir, source)
            dest_path = os.path.join(self.root_dir, destination)
            
            if not os. path.exists(source_path):
                return {"success": False, "error": f"Source not found: {source}"}
            
            # Create destination directory if needed
            os.makedirs(os.path. dirname(dest_path) if os.path.dirname(destination) else self.root_dir, exist_ok=True)
            
            if os.path.isfile(source_path):
                shutil.copy2(source_path, dest_path)
                # Index the new file
                self.vector_store.index_file(dest_path, self.root_dir)
            else:
                shutil.copytree(source_path, dest_path)
            
            return {
                "success": True,
                "message": f"Copied {source} to {destination}"
            }
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def reindex_all(self) -> Dict[str, Any]:
        """Re-index all files in root directory"""
        try:
            stats = self.vector_store.index_directory(self.root_dir)
            return {
                "success": True,
                "stats": stats,
                "message": (
                    f"Re-indexed {stats['indexed']} files"
                    f" ({stats.get('metadata_indexed', 0)} metadata-only protected files)"
                )
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_stats(self) -> Dict[str, Any]:
        """Get file system statistics"""
        vs_stats = self.vector_store. get_stats()
        
        # Count actual files in root
        total_files = 0
        total_dirs = 0
        total_size = 0
        
        for root, dirs, files in os.walk(self.root_dir):
            dirs[:] = [d for d in dirs if not d.startswith('. ')]
            total_dirs += len(dirs)
            for file in files:
                if not file.startswith('.'):
                    total_files += 1
                    try:
                        total_size += os.path.getsize(os. path.join(root, file))
                    except OSError:
                        logger.warning("Unable to read file size during stats: %s", os.path.join(root, file))
        
        return {
            "root_directory": self.root_dir,
            "total_files": total_files,
            "total_directories": total_dirs,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "indexed_files": vs_stats['total_files'],
            "ollama_model": self.config.ollama_model,
            "embedding_model": self.config.embedding_model,
            "versioning_enabled": self.config.enable_versioning
        }
    
    def process_natural_language(self, user_input: str) -> Dict[str, Any]:
        """Process natural language command with search fallback."""
        
        # Parse command with LLM
        parsed = self.llm.parse_command(user_input)
        raw_ollama_output = (
            parsed.get('raw_ollama_output')
            or parsed.get('parameters', {}).get('raw_ollama_output')
        )

        # If the LLM is uncertain or errors out, fall back to semantic search
        # with the original input as query.  This makes the assistant useful
        # even when the model cannot parse a formal command.
        if parsed.get('operation') in ('error', None) or parsed.get('confidence', 0) < 0.5:
            search_results = self.search_files(query=user_input, k=5)
            if search_results.get('success') and search_results.get('results'):
                return {
                    "success": True,
                    "query": user_input,
                    "results": search_results['results'],
                    "count": search_results.get('count', 0),
                    "source": "semantic_fallback",
                    "message": f"Found {search_results.get('count', 0)} results for your query.",
                    "ollama_output": raw_ollama_output,
                }
            return {
                "success": False,
                "error": parsed.get('parameters', {}).get('message', 'LLM request failed'),
                "ollama_output": raw_ollama_output,
            }

        operation = parsed['operation']
        # Normalize common aliases from model output.
        operation_aliases = {
            "find": "search",
            "remove": "delete",
            "mkdir": "create_dir",
            "make_dir": "create_dir",
        }
        operation = operation_aliases.get(operation, operation)
        params = parsed.get('parameters', {})

        if operation == 'chat':
            return {
                "success": True,
                "message": params.get('message', 'I can help with file operations and search.'),
                "operation": operation,
                "parameters": params,
                "results": [],
                "ollama_output": raw_ollama_output,
            }
        
        # Execute operation
        result = self._execute_operation(operation, params)
        result['operation'] = operation
        result['parameters'] = params
        result['ollama_output'] = raw_ollama_output
        
        # Generate friendly response
        if result.get('success'):
            summary = self.llm.summarize_results(operation, result)
            result['summary'] = summary
        
        return result
    
    def _execute_operation(self, operation: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute parsed operation"""
        
        operations = {
            'create_file': lambda: self.create_file(
                params.get('file_name', 'untitled.txt'), 
                params.get('content', '')
            ),
            'create_dir': lambda: self.create_directory(
                params.get('dir_name', 'new_folder')
            ),
            'write':  lambda: self.write_file(
                params.get('file_name'), 
                params.get('content', ''),
                params.get('append', False)
            ),
            'read': lambda: self.read_file(
                params.get('file_name')
            ),
            'search':  lambda: self.search_files(
                params.get('query'), 
                params.get('k', 5), 
                params.get('keywords')
            ),
            'list': lambda: self.list_files(
                params.get('subdir', '')
            ),
            'delete':  lambda: self.delete_file(
                params.get('file_name')
            ),
            'move': lambda: self.move_file(
                params.get('source'),
                params.get('destination')
            ),
            'copy': lambda: self.copy_file(
                params.get('source'),
                params.get('destination')
            ),
            'reindex': lambda: self.reindex_all(),
            'stats': lambda: {"success": True, "stats": self.get_stats()}
        }
        
        if operation in operations:
            try:
                return operations[operation]()
            except TypeError as e:
                return {
                    "success": False, 
                    "error": f"Missing required parameter for {operation}. Try again with more details."
                }
        else:
            return {"success": False, "error": f"Unknown operation: {operation}"}
