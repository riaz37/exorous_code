from __future__ import annotations
from pathlib import Path
from exorous.config.loader import get_data_dir
from exorous.context.vector_db import VectorDBManager
from exorous.tools.base import Tool, ToolInvocation, ToolKind, ToolResult
from pydantic import BaseModel, Field


class CodeSearchParams(BaseModel):
    query: str = Field(..., description="Semantic query to search for in the codebase")
    n_results: int = Field(5, description="Number of results to return (default: 5)")


class CodeSearchTool(Tool):
    name = "code_search"
    description = "Perform a semantic search across the codebase to find relevant code snippets based on meaning."
    kind = ToolKind.READ
    schema = CodeSearchParams

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        params = CodeSearchParams(**invocation.params)
        
        data_dir = get_data_dir()
        project_path = Path(invocation.cwd)
        
        # Initialize manager - in a real production app, this would be pre-initialized
        vdb = VectorDBManager(data_dir, project_path)
        
        try:
            results = vdb.search(params.query, n_results=params.n_results)
            
            if not results:
                return ToolResult.success_result("No relevant code found for the query.")
            
            output = []
            for res in results:
                meta = res["metadata"]
                output.append(f"=== {meta['file_path']} (Lines {meta['start_line']}-{meta['end_line']}) ===")
                output.append(res["content"])
                output.append("")
                
            return ToolResult.success_result(
                "\n".join(output),
                metadata={
                    "query": params.query,
                    "results_count": len(results)
                }
            )
        except Exception as e:
            return ToolResult.error_result(f"Error during code search: {e}")
