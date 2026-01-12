from __future__ import annotations
import hashlib
import os
from pathlib import Path
from typing import Any, List, Optional
import chromadb
from chromadb.utils import embedding_functions
from chromadb.config import Settings
import logging
import ast

logger = logging.getLogger(__name__)

class VectorDBManager:
    """
    Manages semantic indexing and search for the codebase using ChromaDB.
    Supports incremental indexing based on file hashes.
    """

    def __init__(self, data_dir: Path, project_path: Path):
        self.data_dir = data_dir
        self.project_path = project_path
        self.db_path = data_dir / "vector_db"
        self.db_path.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=str(self.db_path),
            settings=Settings(allow_reset=True, anonymized_telemetry=False)
        )

        # Using a reliable local embedding model
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )

        self.collection = self.client.get_or_create_collection(
            name="codebase_intelligence",
            embedding_function=self.embedding_fn,
            metadata={"hnsw:space": "cosine"}
        )

    def _calculate_hash(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _chunk_content(self, content: str, file_path: str, chunk_size: int = 1500) -> List[dict]:
        """
        Intelligently chunks content. Uses AST for Python, fallback to line-based.
        """
        if file_path.endswith(".py"):
            try:
                return self._python_chunker(content, file_path, chunk_size)
            except Exception as e:
                logger.warning(f"AST chunking failed for {file_path}, falling back to line-based: {e}")

        return self._line_chunker(content, chunk_size)

    def _python_chunker(self, content: str, file_path: str, chunk_size: int) -> List[dict]:
        """
        Chunks Python code based on classes and functions using AST.
        """
        tree = ast.parse(content)
        chunks = []
        lines = content.splitlines()

        class ChunkVisitor(ast.NodeVisitor):
            def __init__(self):
                self.found_nodes = []

            def visit_FunctionDef(self, node):
                self.found_nodes.append(node)
                # Don't recurse into nested functions for top-level chunking
            
            def visit_AsyncFunctionDef(self, node):
                self.found_nodes.append(node)

            def visit_ClassDef(self, node):
                self.found_nodes.append(node)
                # Don't recurse into methods for class-level chunking

        visitor = ChunkVisitor()
        visitor.visit(tree)

        last_line = 0
        for node in visitor.found_nodes:
            # Add any gap between the last node and this one as a chunk if it's significant
            if node.lineno > last_line + 1:
                gap_content = "\n".join(lines[last_line:node.lineno-1])
                if gap_content.strip():
                    chunks.append({
                        "content": gap_content,
                        "start_line": last_line + 1,
                        "end_line": node.lineno - 1
                    })

            # Add the function/class itself as a chunk
            node_end = getattr(node, "end_lineno", node.lineno + 1) # end_lineno is 3.8+
            node_content = "\n".join(lines[node.lineno-1:node_end])
            chunks.append({
                "content": node_content,
                "start_line": node.lineno,
                "end_line": node_end
            })
            last_line = node_end

        # Add remaining content
        if last_line < len(lines):
            remaining = "\n".join(lines[last_line:])
            if remaining.strip():
                chunks.append({
                    "content": remaining,
                    "start_line": last_line + 1,
                    "end_line": len(lines)
                })

        return chunks

    def _line_chunker(self, content: str, chunk_size: int) -> List[dict]:
        lines = content.splitlines()
        chunks = []
        current_chunk = []
        current_size = 0
        start_line = 1

        for i, line in enumerate(lines):
            line_size = len(line)
            if current_size + line_size > chunk_size and current_chunk:
                chunks.append({
                    "content": "\n".join(current_chunk),
                    "start_line": start_line,
                    "end_line": i
                })
                current_chunk = []
                current_size = 0
                start_line = i + 1
            
            current_chunk.append(line)
            current_size += line_size

        if current_chunk:
            chunks.append({
                "content": "\n".join(current_chunk),
                "start_line": start_line,
                "end_line": len(lines)
            })

        return chunks

    def index_file(self, file_path: Path) -> bool:
        """
        Indexes a single file if it has changed.
        Returns True if indexed/updated, False otherwise.
        """
        try:
            if not file_path.is_file():
                return False

            rel_path = str(file_path.relative_to(self.project_path))
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            content_hash = self._calculate_hash(content)

            # Check if already indexed and unchanged
            existing = self.collection.get(
                where={"file_path": rel_path},
                include=["metadatas"]
            )

            if existing["ids"]:
                # Assume if one chunk exists, they all have the same hash
                last_hash = existing["metadatas"][0].get("hash")
                if last_hash == content_hash:
                    return False
                
                # If changed, remove old entries
                self.collection.delete(where={"file_path": rel_path})

            chunks = self._chunk_content(content, rel_path)
            if not chunks:
                return False
            
            ids = [f"{rel_path}_{c['start_line']}" for c in chunks]
            documents = [c["content"] for c in chunks]
            metadatas = [{
                "file_path": rel_path,
                "start_line": c["start_line"],
                "end_line": c["end_line"],
                "hash": content_hash
            } for c in chunks]

            self.collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas
            )
            return True

        except Exception as e:
            logger.error(f"Error indexing {file_path}: {e}")
            return False

    def search(self, query: str, n_results: int = 5) -> List[dict]:
        """
        Performs semantic search across the indexed codebase.
        """
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results
        )

        formatted_results = []
        if results["documents"]:
            for i in range(len(results["documents"][0])):
                formatted_results.append({
                    "content": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "distance": results["distances"][0][i] if results["distances"] else None
                })
        
        return formatted_results

    def delete_file(self, rel_path: str):
        self.collection.delete(where={"file_path": rel_path})

    def reset_index(self):
        self.client.reset()
        self.collection = self.client.get_or_create_collection(
            name="codebase_intelligence",
            embedding_function=self.embedding_fn
        )
