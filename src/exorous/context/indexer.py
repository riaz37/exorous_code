from __future__ import annotations
import asyncio
from pathlib import Path
import logging
from typing import Optional
from exorous.context.vector_db import VectorDBManager
from exorous.context.graph import CodeGraphManager
from exorous.utils.paths import is_binary_file
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logger = logging.getLogger(__name__)

class IndexingWorker:
    """
    Handles background indexing of the codebase.
    """

    EXCLUDED_DIRS = {
        ".git", ".venv", "venv", "node_modules", "__pycache__", 
        "dist", "build", ".egg-info", ".ai-agent", ".exorous"
    }
    
    EXCLUDED_EXTENSIONS = {
        '.pyc', '.pyo', '.pyd', '.so', '.dll', '.exe', 
        '.bin', '.dat', '.db', '.sqlite', '.vector_db'
    }

    def __init__(self, vdb_manager: VectorDBManager, graph_manager: CodeGraphManager):
        self.vdb = vdb_manager
        self.graph = graph_manager
        self._indexing_task: Optional[asyncio.Task] = None
        self._observer: Optional[Observer] = None

    async def start(self):
        """Starts the indexing process and file watcher in the background."""
        if self._indexing_task and not self._indexing_task.done():
            return
        
        self._indexing_task = asyncio.create_task(self.index_project())
        self._start_watcher()

    def _start_watcher(self):
        """Initializes and starts the file system watcher."""
        event_handler = IndexingHandler(self)
        self._observer = Observer()
        self._observer.schedule(event_handler, str(self.vdb.project_path), recursive=True)
        self._observer.start()
        logger.info("File system watcher started.")

    def stop(self):
        """Stops the file watcher."""
        if self._observer:
            self._observer.stop()
            self._observer.join()

    async def index_project(self):
        """Scans and indexes the entire project."""
        logger.info(f"Starting codebase indexing for {self.vdb.project_path}")
        
        files_to_index = self._find_files(self.vdb.project_path)
        count = 0
        
        for file_path in files_to_index:
            try:
                # Give some time for other async tasks
                await asyncio.sleep(0.01) 
                
                if self.vdb.index_file(file_path):
                    count += 1
                
                # Also update symbol graph for Python files
                if file_path.suffix == ".py":
                    self.graph.add_file_symbols(file_path)
            except Exception as e:
                logger.error(f"Failed to index {file_path}: {e}")

        logger.info(f"Indexing complete. {count} files updated/added.")

    def _find_files(self, path: Path) -> list[Path]:
        files = []
        for p in path.rglob("*"):
            if not p.is_file():
                continue
            
            # Check if any parent is excluded
            if any(part in self.EXCLUDED_DIRS for part in p.parts):
                continue
                
            if p.suffix.lower() in self.EXCLUDED_EXTENSIONS:
                continue
                
            if is_binary_file(p):
                continue
                
            files.append(p)
        return files

    async def watch_changes(self):
        """
        No longer needed as start() now initializes the watchdog Observer.
        """
        pass

class IndexingHandler(FileSystemEventHandler):
    """
    Handles file system events to trigger re-indexing.
    """
    def __init__(self, worker: IndexingWorker):
        self.worker = worker
        self.loop = asyncio.get_event_loop()

    def on_modified(self, event):
        if not event.is_directory:
            self._trigger_reindex(event.src_path)

    def on_created(self, event):
        if not event.is_directory:
            self._trigger_reindex(event.src_path)

    def on_deleted(self, event):
        if not event.is_directory:
            rel_path = str(Path(event.src_path).relative_to(self.worker.vdb.project_path))
            self.worker.vdb.delete_file(rel_path)

    def _trigger_reindex(self, file_path_str: str):
        file_path = Path(file_path_str)
        # Check if file should be ignored
        if any(part in self.worker.EXCLUDED_DIRS for part in file_path.parts):
            return
        if file_path.suffix.lower() in self.worker.EXCLUDED_EXTENSIONS:
            return
            
        # Run indexing in the background without blocking the watcher
        self.loop.call_soon_threadsafe(self.worker.vdb.index_file, file_path)
        if file_path.suffix == ".py":
            self.loop.call_soon_threadsafe(self.worker.graph.add_file_symbols, file_path)
