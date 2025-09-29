# Smart Sort

> **AI-Powered Semantic File Organization System**

Smart Sort is an intelligent file organization tool that leverages machine learning and natural language processing to automatically categorize and sort files based on their semantic content, not just file types. Built with a modern tech stack combining Python AI/ML capabilities with a sleek Tauri desktop application.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Tauri](https://img.shields.io/badge/tauri-2.x-orange.svg)](https://tauri.app/)
[![SvelteKit](https://img.shields.io/badge/svelte-kit-red.svg)](https://kit.svelte.dev/)

## Features

### Intelligent Content Analysis
- **Multi-format Support**: PDF, DOCX, TXT, images (with OCR), and code files
- **Semantic Understanding**: Uses sentence transformers for deep content comprehension
- **AI-Powered Naming**: GPT-based folder naming for intuitive organization

### Advanced Processing Pipeline
- **6-Stage Pipeline**: Ingestion → Extraction → Embedding → Clustering → Naming → Relocation
- **HDBSCAN Clustering**: Automatically groups semantically similar files
- **Preview Mode**: See organization structure before applying changes
- **Progress Tracking**: Real-time feedback during processing

### Modern Desktop Experience
- **Cross-Platform**: Built with Tauri for native performance on macOS, Windows, and Linux
- **Intuitive UI**: Interface with live preview
- **Custom Typography**: Jacquard24 and Electrolize font integration
- **Dark/Light Themes**: Adaptive interface design

## Technology Stack

### Backend (Python)
- **Machine Learning**: `sentence-transformers`, `HDBSCAN`, `scikit-learn`
- **AI Integration**: OpenAI GPT for intelligent naming
- **Document Processing**: `PyPDF2`, `python-docx`, `pytesseract` (OCR)
- **Data Processing**: `pandas`, `numpy`

### Frontend (Tauri + SvelteKit)
- **Desktop Framework**: Tauri 2.x (Rust-based)
- **Web Framework**: SvelteKit with TypeScript
- **Build Tools**: Vite, PNPM
- **UI/UX**: Custom CSS with modern design principles

### Development & Testing
- **Testing**: pytest with comprehensive test coverage
- **Code Quality**: Modular architecture with separation of concerns
- **Virtual Environment**: Isolated Python dependencies

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Rust (for Tauri builds)
- PNPM (recommended) or NPM

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/Tommy-Parisi/FileSorter.git
   cd FileSorter
   ```

2. **Set up Python environment**
   ```bash
   # Create and activate virtual environment
   python -m venv fileSortVenv
   source fileSortVenv/bin/activate  # On Windows: fileSortVenv\Scripts\activate
   
   # Install dependencies
   cd backend
   pip install -r requirements.txt
   ```

3. **Set up frontend**
   ```bash
   cd ../frontend
   pnpm install
   ```

4. **Configure environment variables**
   ```bash
   # Copy and configure your OpenAI API key
   cp .env.example .env
   # Edit .env and add your OPENAI_API_KEY
   ```

### Running the Application

#### Development Mode
```bash
# Frontend development server
cd frontend
pnpm run tauri dev
```

#### Production Build
```bash
# Build the desktop application
cd frontend
pnpm run tauri build
```

#### Command Line Interface
```bash
# Run via CLI (for testing/automation)
cd backend
python -m pipeline.cli /path/to/your/files
```

## Usage

1. **Launch the application** and select a folder containing mixed file types
2. **Configure settings** (clustering parameters, naming style, etc.)
3. **Preview organization** to see how files will be grouped
4. **Run the sorter** to apply the intelligent organization
5. **Open results** directly in your file manager

## Testing

Run the comprehensive test suite:

```bash
# Run all tests
cd backend
./fileSortVenv/bin/python -m pytest tests/ -v

# Run specific test modules
./fileSortVenv/bin/python -m pytest tests/test_clustering.py -vv
./fileSortVenv/bin/python -m pytest tests/test_embedding.py -vv
```

## Architecture

### Pipeline Architecture
```
Input Files → Ingestion → Content Extraction → Embedding Generation 
                                                        ↓
Organized Folders ← File Relocation ← Folder Naming ← Clustering
```

### Key Components

- **`ingestion_manager.py`**: File discovery and validation
- **`extractors/`**: Content extraction for various file types
- **`embedding_agent.py`**: Semantic vector generation
- **`clustering_agent.py`**: HDBSCAN-based file grouping
- **`folder_naming_agent.py`**: AI-powered folder naming
- **`file_relocation_agent.py`**: Safe file organization

## Contributing

I am happy to take contributions! 
Just make a pull request!

### Development Guidelines
- Follow PEP 8 for Python code
- Add type hints where appropriate
- Include tests for new features
- Update documentation as needed
- Ensure cross-platform compatibility

## Performance & Scalability

- **Batch Processing**: Efficient handling of large file collections
- **Memory Management**: Optimized for minimal resource usage
- **Caching**: Intelligent caching of embeddings and metadata

## Security & Privacy

- **Local Processing**: All file analysis happens on your machine
- **API Security**: Secure handling of OpenAI API keys
- **File Safety**: Non-destructive operations with backup capabilities
- **Permission Management**: Proper file system permissions

## Roadmap

- [ ] **Cross-Platform Installers**: Native installers for Windows (.msi), macOS (.dmg), and Linux (.AppImage)
- [ ] **Batch Operations**: Multiple folder processing
- [ ] **Custom Models**: Support for local embedding models

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- **Hugging Face**: For sentence-transformer models
- **OpenAI**: For GPT integration capabilities
- **Tauri Team**: For the excellent desktop framework
- **SvelteKit**: For the modern web development experience

## Contact

**Tommy Parisi** - [GitHub](https://github.com/Tommy-Parisi)
**My Website** - tommyparisi.com

Project Link: [https://github.com/Tommy-Parisi/FileSorter](https://github.com/Tommy-Parisi/FileSorter)
