#!/usr/bin/env python3
"""
Local LSFS Terminal Interface
A natural language file system powered by local LLMs
"""

import sys
import os
from typing import Optional
from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style
from prompt_toolkit. formatted_text import HTML
from rich.console import Console
from rich. table import Table
from rich.panel import Panel
from rich.syntax import Syntax
from rich.markdown import Markdown
from rich import box

# Add lsfs to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lsfs.file_system import LocalLSFS
from lsfs.config import LSFSConfig

# Optional: Load from YAML
try:
    from lsfs. config_loader import load_config_from_yaml
    USE_YAML = True
except ImportError:
    USE_YAML = False

class LSFSTerminal:
    """Interactive terminal for LSFS"""
    
    def __init__(self, config: LSFSConfig):
        self.console = Console()
        self.lsfs = None
        self.config = config
        self.session = PromptSession()
        
        # Custom prompt style
        self.prompt_style = Style. from_dict({
            'prompt': '#00aa00 bold',
            'path': '#0088ff',
        })
    
    def display_banner(self):
        """Display welcome banner"""
        banner = """
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║        🌟 Local LSFS - LLM Semantic File System 🌟       ║
║                                                           ║
║        Talk to your files in natural language            ║
║        Powered by Ollama + ChromaDB                      ║
║        Version Control:  DISABLED (No Redis needed)       ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
"""
        self.console.print(banner, style="cyan bold")
    
    def display_help(self):
        """Display help information"""
        help_text = """
# 📚 LSFS Commands & Examples

## File Operations
• **Create file**:  "create a file called notes.txt"
• **Write to file**: "write 'hello world' to test.txt"
• **Read file**: "read notes.txt" or "show me test.txt"
• **Delete file**: "delete old_file. txt"
• **Move file**: "move report.txt to docs/report.txt"
• **Copy file**: "copy notes.txt to backup/notes.txt"

## Directory Operations
• **Create directory**: "create a folder called documents"
• **List files**: "list all files" or "show files in documents"

## Semantic Search (The Magic!  ✨)
• **Search by content**: "search for files about machine learning"
• **Find similar files**: "find 3 files related to python programming"
• **Keyword search**: "search for files containing 'database' keyword"

## System Commands
• **Stats**: "stats" or "show statistics"
• **Reindex**: "reindex all files" - Rebuild search index
• **Help**: "help" - Show this message
• **Clear**: "clear" - Clear screen
• **Exit**: "exit" or "quit" - Exit LSFS

## Tips
💡 Just type naturally! The LLM understands your intent.
💡 Files are automatically indexed for semantic search.
💡 No version control (Redis disabled for simplicity).
💡 Try "search for files about X" to test semantic search! 
"""
        self.console.print(Panel(Markdown(help_text), title="Help", border_style="blue"))
    
    def _display_search_results(self, result: dict):
        """Display semantic search results"""
        results = result.get('results', [])
        query = result.get('query', '')
        
        if not results: 
            self.console.print(f"\n🔍 No files found matching:  '{query}'\n", style="yellow")
            return
        
        self.console.print(f"\n🔍 Search Results for:  '{query}' ({len(results)} files)\n", style="cyan bold")
        
        table = Table(show_header=True, header_style="bold magenta", box=box.ROUNDED)
        table.add_column("📁 File", style="cyan", width=40)
        table.add_column("📊 Score", justify="right", style="green", width=10)
        table.add_column("📝 Preview", style="white", width=50)
        
        for i, item in enumerate(results, 1):
            score = f"{item. get('score', 0):.2%}"
            preview_raw = item.get('preview', '')
            preview = preview_raw[:100] + "..." if len(preview_raw) > 100 else preview_raw
            rel_path = item.get('relative_path', 'Unknown')
            abs_path = os.path.abspath(os.path.join(self.config.root_dir, rel_path))
            # clickable hyperlink for terminals that support OSC 8 (Rich renders links)
            link = f"[link=file:///{abs_path.replace(os.sep, '/')}]{rel_path}[/link]"
            table.add_row(
                link,
                score,
                preview
            )
        
        self.console.print(table)
        self.console.print()

    def _detect_result_type(self, result: dict) -> str:
        """Detect what type of operation result this is"""
        if not isinstance(result, dict):
            return 'generic'
        if 'results' in result and 'query' in result:
            return 'search'
        if 'content' in result and 'file_name' in result:
            return 'read'
        if 'files' in result and 'directories' in result:
            return 'list'
        if 'stats' in result:
            return 'stats'
        return 'generic'

    def display_result(self, result: dict):
        """Route result to the right renderer"""
        kind = self._detect_result_type(result)
        if kind == 'search':
            self._display_search_results(result)
        elif kind == 'read':
            self._display_file_content(result)
        elif kind == 'list':
            self._display_file_list(result)
        elif kind == 'stats':
            self._display_stats(result)
        else:
            self.console.print(result)
        self.console.print()
    
    def _display_file_content(self, result:  dict):
        """Display file content with syntax highlighting"""
        file_name = result.get('file_name', 'file')
        content = result.get('content', '')
        
        self.console.print(f"\n📄 Content of:  {file_name}\n", style="cyan bold")
        
        # Try to detect language for syntax highlighting
        extension = os.path.splitext(file_name)[1]
        lexer_map = {
            '.py': 'python',
            '.js': 'javascript',
            '. json': 'json',
            '. md': 'markdown',
            '.yml': 'yaml',
            '. yaml': 'yaml',
            '.sh': 'bash',
            '. txt': 'text',
            '. html': 'html',
            '. css': 'css',
            '.sql': 'sql'
        }
        
        lexer = lexer_map.get(extension, 'text')
        
        if len(content) > 5000:
            self.console.print(f"[yellow]⚠️  Large file ({len(content)} chars). Showing first 5000 characters.. .[/yellow]\n")
            content = content[:5000] + "\n\n[...  truncated ...]"
        
        syntax = Syntax(content, lexer, theme="monokai", line_numbers=True)
        self.console.print(Panel(syntax, border_style="blue"))
        self.console.print()
    
    def _display_file_list(self, result: dict):
        """Display file listing"""
        files = result.get('files', [])
        directories = result.get('directories', [])
        path = result.get('path', '/')
        
        self.console.print(f"\n📂 Directory: {path}\n", style="cyan bold")
        
        if directories:
            self.console.print("📁 Directories:", style="blue bold")
            for dir_name in directories:
                self.console. print(f"  └─ {dir_name}/", style="blue")
            self.console.print()
        
        if files:
            table = Table(show_header=True, header_style="bold magenta", box=box.SIMPLE)
            table.add_column("📄 File Name", style="cyan")
            table.add_column("📦 Size", justify="right", style="green")
            table.add_column("🕐 Modified", style="yellow")
            
            for file in files:
                size_bytes = file.get('size', 0)
                if size_bytes < 1024:
                    size_str = f"{size_bytes} B"
                elif size_bytes < 1024 * 1024:
                    size_str = f"{size_bytes/1024:.2f} KB"
                else: 
                    size_str = f"{size_bytes/(1024*1024):.2f} MB"
                
                modified = file.get('modified', '')[: 19]. replace('T', ' ')
                table.add_row(file.get('name', ''), size_str, modified)
            
            self.console.print(table)
        
        if not files and not directories:
            self.console.print("📭 Empty directory\n", style="yellow")
        else:
            total = result.get('total', 0)
            self.console.print(f"\nTotal:  {total} items\n", style="green")
    
    def _display_stats(self, result: dict):
        """Display system statistics"""
        stats = result.get('stats', {})
        
        self. console.print("\n📊 LSFS Statistics\n", style="cyan bold")
        
        table = Table(show_header=False, box=box.ROUNDED)
        table.add_column("Property", style="cyan bold")
        table.add_column("Value", style="green")
        
        table.add_row("📁 Root Directory", stats.get('root_directory', 'N/A'))
        table.add_row("🤖 LLM Model", stats.get('ollama_model', 'N/A'))
        table.add_row("🧠 Embedding Model", stats. get('embedding_model', 'N/A'))
        table.add_row("📄 Total Files", str(stats.get('total_files', 0)))
        table.add_row("📂 Total Directories", str(stats.get('total_directories', 0)))
        table.add_row("💾 Total Size", f"{stats.get('total_size_mb', 0)} MB")
        table.add_row("🔍 Indexed Files", str(stats.get('indexed_files', 0)))
        table.add_row("🔄 Versioning", "Disabled" if not stats.get('versioning_enabled') else "Enabled")
        
        self.console.print(table)
        self.console.print()
    
    def get_prompt(self) -> str:
        """Get formatted prompt"""
        root_name = os.path.basename(self.config.root_dir)
        return HTML(f'<prompt>lsfs</prompt>: <path>{root_name}</path>$ ')
    
    def initialize_lsfs(self):
        """Initialize LSFS with loading animation"""
        try:
            with self.console.status("[cyan]Initializing LSFS...", spinner="dots"):
                self.lsfs = LocalLSFS(self. config)
            return True
        except Exception as e: 
            self.console.print(f"\n❌ Failed to initialize LSFS: {e}\n", style="red bold")
            self.console.print("💡 Make sure Ollama is running:  ollama serve\n", style="yellow")
            self.console.print(f"💡 Or check if model '{self.config.ollama_model}' is installed\n", style="yellow")
            return False
    
    def run(self):
        """Main terminal loop"""
        self.display_banner()
        
        # Initialize LSFS
        if not self.initialize_lsfs():
            return
        
        self.console.print("\n✨ Type 'help' for commands or just ask naturally!\n", style="green")
        self.console.print("Example: 'search for files about python'\n", style="dim")
        
        while True: 
            try:
                # Get user input
                user_input = self.session.prompt(
                    self.get_prompt(),
                    style=self.prompt_style
                ).strip()
                
                if not user_input:
                    continue
                
                # Check for special commands
                if user_input. lower() in ['exit', 'quit', 'q']:
                    self.console. print("\n👋 Goodbye!\n", style="cyan bold")
                    break
                
                elif user_input.lower() == 'help':
                    self.display_help()
                    continue
                
                elif user_input.lower() == 'clear':
                    os.system('clear' if os.name != 'nt' else 'cls')
                    self.display_banner()
                    continue
                
                # Process with LLM
                with self.console.status("[cyan]Processing.. .", spinner="dots"):
                    result = self.lsfs.process_natural_language(user_input)
                
                # Display result
                self.display_result(result)
            
            except KeyboardInterrupt: 
                self.console.print("\n\n👋 Goodbye!\n", style="cyan bold")
                break
            
            except EOFError:
                break
            
            except Exception as e:
                self.console.print(f"\n❌ Error: {e}\n", style="red bold")

def main():
    """Entry point"""
    
    # Try to load config from YAML
    if USE_YAML and os.path.exists('config.yaml'):
        config = load_config_from_yaml('config.yaml')
    else:
        config = LSFSConfig()
    
    # Start terminal
    terminal = LSFSTerminal(config)
    terminal.run()

if __name__ == "__main__":
    main()