# Changelog

## [0.2.0] - 2026-01-12

### Added
- **Advanced Context & Codebase Intelligence Layer**:
    - **Semantic Search (RAG)**: Integrated ChromaDB for local semantic indexing of the entire codebase.
    - **AST-based Chunking**: Implemented intelligent Python code splitting for superior search relevance.
    - **Knowledge Graph**: Built a symbol map using Jedi and NetworkX, tracking functions, classes, and cross-file imports.
    - **Real-time Synchronization**: Added `watchdog` integration for automatic background re-indexing on file changes.
    - **Long-Term Memory**: Persistent, project-specific knowledge store for conventions and design decisions.
    - **New Tool**: `code_search` for semantic exploration of the codebase.
- **Enhanced `memory` Tool**: Support for `scope="project"` to store persistent project-wide notes.

### Fixed
- Fixed Jedi API mismatches in symbol analysis.
- Improved error handling for empty files and binary files during indexing.
- Resolved missing `Path` and utility imports in 여러 components.

## [0.1.0] - 2026-01-01
- Initial release with basic tool set and agentic capabilities.
