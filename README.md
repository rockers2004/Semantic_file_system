# Local LSFS - Semantic File System

A natural language-powered file system that uses local LLMs (Large Language Models) to intelligently search, organize, and manage files. Ask questions in plain English and get results based on semantic understanding of your file contents.

## Overview

**Local LSFS** (Local Large Language Model Semantic File System) is a Python-based application that combines:
- **Local LLMs** (via Ollama) - Process files without sending data to the cloud
- **Vector Embeddings** - Create semantic understanding of file content
- **Natural Language Interface** - Query files using plain English
- **Fast Search** - Find files by meaning, not just keywords

## Key Features

✨ **Natural Language Search** - Search files using natural language queries  
🔒 **Privacy-First** - Runs completely locally, no cloud dependencies  
⚡ **Fast Embeddings** - Uses lightweight `all-MiniLM-L6-v2` model  
🤖 **Local LLM Support** - Works with Ollama and any compatible model  
💾 **Vector Database** - ChromaDB for efficient semantic search  
🎨 **Interactive Terminal UI** - Beautiful CLI interface with Rich formatting  

## Prerequisites

Before you start, ensure you have:

- **Python 3.8+** installed
- **Ollama** installed and running locally ([Download here](https://ollama.ai))
- A local LLM model (e.g., `tinyllama:latest` or your preferred model)

### Check Ollama Setup

```bash
# Start Ollama service
ollama serve

# In another terminal, pull a model (if not already done)
ollama pull tinyllama:latest
```

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/taslim121/Semantic_file_system.git
cd local-lsfs
```

### 2. Create a Virtual Environment (Recommended)

```bash
# On Windows
python -m venv venv
venv\Scripts\activate

# On macOS/Linux
python -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

**Dependencies:**
- `chromadb==0.4.22` - Vector database for embeddings
- `sentence-transformers==2.3.1` - Lightweight embedding model
- `requests==2.31.0` - HTTP client for Ollama API
- `prompt-toolkit==3.0.43` - Interactive terminal input
- `rich==13.7.0` - Beautiful terminal formatting
- `numpy==1.24.3` - Numerical operations
- `nltk==3.8.1` - Natural language utilities

## Configuration

Edit `config.yaml` to customize your setup:

```yaml
# Root directory to index and search
root_dir: "C:/Users/YourUser/Desktop/your-folder"

# Where ChromaDB stores vector data
vector_db_dir: "./.lsfs_db"

# LLM Settings
ollama:
  model: "tinyllama:latest"        # Change to your preferred model
  url: "http://localhost:11434"    # Ollama server address

# Embedding model (lightweight, ~80MB)
embedding:
  model: "all-MiniLM-L6-v2"

# Search Settings
search:
  default_results: 5               # Number of results to return
  max_file_size_mb: 10            # Skip files larger than this

# Performance
performance:
  enable_caching: true
```

### Configuration Options

| Setting | Purpose | Default |
|---------|---------|---------|
| `root_dir` | The folder to index and search | Desktop test folder |
| `vector_db_dir` | Vector database storage location | `./.lsfs_db` |
| `ollama.model` | LLM model to use | `tinyllama:latest` |
| `embedding.model` | Embedding model | `all-MiniLM-L6-v2` |
| `search.default_results` | Results per query | 5 |
| `max_file_size_mb` | File size limit for indexing | 10 MB |

## Usage

### Start the Interactive Terminal

```bash
python terminal.py
```

You'll see a welcome banner and a prompt where you can enter natural language queries.

### Example Queries

```
> Search for Python files about machine learning
> Find configuration files
> Show me all JSON files related to API
> List recently modified files
> Find duplicate content across files
```

### Available Commands

- **`search <query>`** - Search files by natural language
- **`index`** - Re-index the entire root directory
- **`status`** - Show current database status
- **`help`** - Show available commands
- **`exit` or `quit`** - Exit the application

## Project Structure

```
local-lsfs/
├── README.md                      # This file
├── config.yaml                    # Configuration file
├── requirements.txt               # Python dependencies
├── terminal.py                    # Main CLI interface
├── lsfs/
│   ├── ___init___.py             # Package initialization
│   ├── config.py                 # Configuration dataclass
│   ├── config_loader.py          # YAML config loader
│   ├── file_system.py            # Core LSFS logic
│   ├── llm_handler.py            # Ollama integration
│   └── vector_store.py           # ChromaDB wrapper
├── lsfs_root/                    # Test directory
└── .lsfs_db/                     # Vector database (auto-created)
```

## How It Works

1. **Indexing** - Files are read and split into chunks
2. **Embedding** - Each chunk is converted to a vector using `sentence-transformers`
3. **Storage** - Vectors are stored in ChromaDB
4. **Query** - User queries are embedded and matched against stored vectors
5. **Re-ranking** - Results are re-ranked using the local LLM

## Troubleshooting

### "Connection refused" Error

```
Error: Could not connect to Ollama at http://localhost:11434
```

**Solution:** Make sure Ollama is running:
```bash
ollama serve
```

### Model Not Found

```
Error: Model 'tinyllama:latest' not found
```

**Solution:** Pull the model from Ollama:
```bash
ollama pull tinyllama:latest
```

### Out of Memory

If your system is slow, try a smaller model:
```bash
ollama pull phi:latest          # Smaller, faster
```

### Vector Database Issues

To reset the vector database:
```bash
rm -rf .lsfs_db              # On macOS/Linux
rmdir /s .lsfs_db            # On Windows
```

Then restart the application.

## Performance Tips

1. **Use smaller models** for faster responses (phi, tinyllama)
2. **Limit file size** in config to avoid processing large files
3. **Enable caching** in config for repeated queries
4. **Index once** and reuse the vector database
5. **Allocate RAM** to Ollama for faster LLM processing

## Future Enhancements

- [ ] Support for more file types (images, videos)
- [ ] Multi-language support
- [ ] Batch file operations
- [ ] File modification tracking
- [ ] Export search results
- [ ] Web UI interface
- [ ] Redis caching support

## License

This project is open source. See the repository for license details.

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Support

For issues, questions, or suggestions:
- Open an issue on GitHub: [Semantic_file_system](https://github.com/taslim121/Semantic_file_system)
- Check existing issues for solutions

## Acknowledgments

- **Ollama** - Local LLM inference
- **ChromaDB** - Vector database
- **Sentence Transformers** - Embedding models
- **Rich** - Beautiful terminal output
