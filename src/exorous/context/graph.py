from __future__ import annotations
from pathlib import Path
import logging
import networkx as nx
import jedi
import json
import os

logger = logging.getLogger(__name__)

class CodeGraphManager:
    """
    Manages a knowledge graph of the codebase symbols (functions, classes, dependencies).
    Uses NetworkX for the graph and Jedi for static analysis.
    """

    def __init__(self, data_dir: Path, project_path: Path):
        self.data_dir = data_dir
        self.project_path = project_path
        self.graph_path = data_dir / "code_graph.json"
        self.graph = nx.DiGraph()
        
        if self.graph_path.exists():
            self._load_graph()

    def _load_graph(self):
        try:
            with open(self.graph_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.graph = nx.node_link_graph(data)
        except Exception as e:
            logger.error(f"Failed to load code graph: {e}")
            self.graph = nx.DiGraph()

    def _save_graph(self):
        try:
            data = nx.node_link_data(self.graph)
            with open(self.graph_path, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception as e:
            logger.error(f"Failed to save code graph: {e}")

    def add_file_symbols(self, file_path: Path):
        """
        Analyzes a file using Jedi and updates the graph.
        """
        try:
            rel_path = str(file_path.relative_to(self.project_path))
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            
            project = jedi.Project(str(self.project_path))
            script = jedi.Script(content, path=str(file_path), project=project)
            
            # File node
            self.graph.add_node(rel_path, type="file")
            
            # Get definitions (classes, functions)
            defs = script.get_names(all_scopes=True, definitions=True)
            for d in defs:
                full_name = f"{rel_path}:{d.full_name}"
                self.graph.add_node(full_name, 
                                   type=d.type, 
                                   name=d.name,
                                   line=d.line,
                                   column=d.column,
                                   file=rel_path)
                self.graph.add_edge(rel_path, full_name, rel="contains")
                
                # Find usages of this definition
                usages = d.goto()
                for usage in usages:
                    if usage.module_path:
                        try:
                            use_rel_path = str(Path(usage.module_path).relative_to(self.project_path))
                            self.graph.add_node(use_rel_path, type="file")
                            self.graph.add_edge(use_rel_path, full_name, rel="references")
                        except ValueError:
                            continue

            # Get imports
            imports = script.get_names(all_scopes=True, definitions=False, references=True)
            for imp in imports:
                if imp.type == 'import':
                    try:
                        resolved = imp.goto()
                        for r in resolved:
                            if r.module_path:
                                try:
                                    imp_rel_path = str(Path(r.module_path).relative_to(self.project_path))
                                    self.graph.add_node(imp_rel_path, type="file")
                                    self.graph.add_edge(rel_path, imp_rel_path, rel="imports")
                                except ValueError:
                                    continue
                    except Exception:
                        continue

            self._save_graph()
        except Exception as e:
            logger.error(f"Error analyzing symbols for {file_path}: {e}")

    def get_impacted_nodes(self, node_id: str) -> list[str]:
        """
        Finds nodes that might be impacted by changes to the given node.
        """
        if node_id not in self.graph:
            return []
        
        # Nodes that call or depend on this node
        return list(self.graph.predecessors(node_id))

    def search_symbols(self, query: str) -> list[dict]:
        """
        Simple keyword search in the graph.
        """
        results = []
        for node, data in self.graph.nodes(data=True):
            if data.get("type") in ["function", "class"] and query.lower() in data.get("name", "").lower():
                results.append({"id": node, **data})
        return results
