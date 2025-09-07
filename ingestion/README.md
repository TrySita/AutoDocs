# Analysis Agent

A Python-based AST parsing and code analysis tool that builds dependency graphs of codebases and generates AI-powered documentation. The tool uses tree-sitter for parsing multiple programming languages, stores structured data in SQLite, and provides intelligent code summarization using Large Language Models.

## Features

- **Multi-language AST Parsing**: Parse JavaScript, TypeScript, JSX, and TSX files using tree-sitter
- **Dependency Graph Construction**: Build function-level and file-level dependency graphs using NetworkX
- **AI-Powered Documentation**: Generate intelligent summaries for files and functions using LLMs
- **Optimal Traversal Order**: Use Z3 solver to find optimal code reading order based on dependencies
- **Cycle Detection**: Handle circular dependencies in codebases gracefully
- **Interactive Visualization**: Generate HTML visualizations of dependency graphs
- **SQLite Persistence**: Store all parsed data in a structured SQLite database

## Installation

### Prerequisites

- Python 3.13 or higher
- Poetry (for dependency management)

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd analysis-agent-new
```

2. Install dependencies using Poetry:
```bash
poetry install
```

3. Activate the virtual environment:
```bash
poetry shell
```

## Usage

### Basic Usage

Parse a directory and generate analysis:

```bash
python -m ast_parsing.main /path/to/your/codebase output.db
```

This will:
1. Parse all supported files in the directory
2. Extract functions, classes, imports, and dependencies
3. Store everything in a SQLite database
4. Build dependency graphs
5. Generate AI summaries for files and functions
6. Create an interactive HTML visualization

### Example Output

After running the tool, you'll see:

```
Directory parsing completed. Results written to output.db
parsed definitions: 142
parsed function calls: 89
parsed imports: 45
parsed types: 67
parsed files: 23
Built function dependency graph with 142 nodes and 89 edges
Optimal traversal order: [1, 5, 12, 8, ...]
AI summaries generated for all files.
Generated 23 file summaries
Generated 142 definition summaries
Total input tokens: {'total_file_input_tokens': 15420, ...}
```

### Project Structure

```
src/
├── ast_parsing/           # Core AST parsing logic
│   ├── main.py           # CLI entry point
│   ├── parser.py         # Main parsing orchestrator
│   ├── language_parser.py # Tree-sitter language management
│   ├── queries/          # Tree-sitter query definitions
│   └── utils/            # Parsing utilities
├── database/             # Data persistence layer
│   ├── models.py         # SQLAlchemy models
│   └── manager.py        # Database connection management
├── dag_builder/          # Dependency graph construction
│   ├── netx.py          # NetworkX graph builders
│   └── z3_solver.py     # Optimal traversal using Z3
└── ai_analysis/         # AI-powered documentation
    └── summaries.py     # LLM integration for summaries
```

## Database Schema

The tool creates several related tables to store parsed information:

- **files**: Source files with content and metadata
- **definitions**: Functions, classes, interfaces, types, etc.
- **function_calls**: Call relationships between definitions
- **imports**: Import statements and their resolutions
- **type_references**: Type usage relationships

## Configuration

### AI Summary Generation

The tool uses Google's Gemini model for generating summaries. Configure your API access in the `ai_analysis/summaries.py` file.

### Supported File Types

Currently supports:
- JavaScript (.js)
- TypeScript (.ts)
- JSX (.jsx)
- TSX (.tsx)

## Testing

Run the test suite:

```bash
poetry run pytest tests/ -v
```

The tests cover:
- AST parsing for different language constructs
- Function call extraction
- Import/export resolution
- Type reference handling
- Database model relationships

## Architecture

### Core Components

1. **AST Parsing Pipeline**: Uses tree-sitter to parse source code into structured data
2. **Database Layer**: SQLAlchemy models for persistent storage
3. **Graph Analysis**: NetworkX for dependency graph construction and analysis
4. **AI Integration**: LLM-powered summarization with dependency-aware generation
5. **Visualization**: Interactive HTML graphs using pyvis

### Key Algorithms

- **Dependency Resolution**: Resolves function calls to their definitions across files
- **Cycle Detection**: Identifies and handles circular dependencies
- **Optimal Traversal**: Uses Z3 SMT solver to find optimal code reading order
- **Recursive Summarization**: Generates summaries respecting dependency order

## Development

### Adding Language Support

To add support for a new programming language:

1. Create query files in `src/ast_parsing/queries/`
2. Add language mapping in `language_parser.py`
3. Update the parser logic to handle language-specific constructs
4. Add tests for the new language

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Run the test suite
5. Submit a pull request

## Dependencies

Key dependencies include:
- `tree-sitter`: AST parsing
- `sqlalchemy`: Database ORM
- `networkx`: Graph analysis
- `z3-solver`: Optimization
- `openai`: AI integration
- `pyvis`: Graph visualization
- `sentence-transformers`: Semantic analysis

## License

This project is licensed under the Apache 2.0 License.

## Recent Changes

- **v0.1.0**: Initial implementation with TypeScript/JavaScript support
- Added AI-powered summarization system
- Implemented Z3-based optimal traversal
- Created interactive dependency visualizations
- Added comprehensive test suite

