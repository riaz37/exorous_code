from __future__ import annotations
from datetime import datetime
import json
from typing import Any
import uuid
from exorous.client.llm_client import LLMGateway
from exorous.config.config import Config
from exorous.config.loader import get_data_dir
from exorous.context.compaction import ChatCompactor
from exorous.context.loop_detector import LoopDetector
from exorous.context.manager import ContextManager
from exorous.hooks.hook_system import HookSystem
from exorous.safety.approval import ApprovalManager
from exorous.tools.discovery import ToolDiscoveryManager
from exorous.tools.mcp.mcp_manager import MCPManager
from exorous.tools.registry import create_default_registry
from exorous.context.vector_db import VectorDBManager
from exorous.context.graph import CodeGraphManager
from exorous.context.knowledge import ProjectKnowledgeStore
from exorous.context.indexer import IndexingWorker


class Session:
    def __init__(self, config: Config):
        self.config = config
        self.client = LLMGateway(config=config)
        self.tool_registry = create_default_registry(config)
        self.context_manager: ContextManager | None = None
        self.discovery_manager = ToolDiscoveryManager(
            self.config,
            self.tool_registry,
        )
        self.mcp_manager = MCPManager(self.config)
        self.chat_compactor = ChatCompactor(self.client)
        self.approval_manager = ApprovalManager(
            self.config.approval,
            self.config.cwd,
        )
        self.loop_detector = LoopDetector()
        self.hook_system = HookSystem(config)
        
        # Intelligence Layer
        self.vdb = VectorDBManager(get_data_dir(), config.cwd)
        self.graph = CodeGraphManager(get_data_dir(), config.cwd)
        self.knowledge = ProjectKnowledgeStore(get_data_dir(), config.cwd)
        self.indexer = IndexingWorker(self.vdb, self.graph)
        
        self.session_id = str(uuid.uuid4())
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

        self.turn_count = 0

    async def initialize(self) -> None:
        await self.mcp_manager.initialize()
        self.mcp_manager.register_tools(self.tool_registry)

        self.discovery_manager.discover_all()
        self.context_manager = ContextManager(
            config=self.config,
            user_memory=self._load_all_memory(),
            tools=self.tool_registry.get_tools(),
        )
        
        # Start background indexing
        await self.indexer.start()

    def _load_all_memory(self) -> str | None:
        user_memory = self._load_user_memory()
        project_knowledge = self.knowledge.get_formatted_knowledge()
        
        memories = []
        if user_memory:
            memories.append(user_memory)
        if project_knowledge:
            memories.append(project_knowledge)
            
        return "\n\n".join(memories) if memories else None

    def _load_user_memory(self) -> str | None:
        data_dir = get_data_dir()
        data_dir.mkdir(parents=True, exist_ok=True)
        path = data_dir / "user_memory.json"

        if not path.exists():
            return None

        try:
            content = path.read_text(encoding="utf-8")
            data = json.loads(content)
            entries = data.get("entries")
            if not entries:
                return None

            lines = ["User preferences and notes:"]
            for key, value in entries.items():
                lines.append(f"- {key}: {value}")

            return "\n".join(lines)
        except Exception:
            return None

    def increment_turn(self) -> int:
        self.turn_count += 1
        self.updated_at = datetime.now()

        return self.turn_count

    def get_stats(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "turn_count": self.turn_count,
            "message_count": self.context_manager.message_count,
            "token_usage": self.context_manager.total_usage,
            "tools_count": len(self.tool_registry.get_tools()),
            "mcp_servers": len(self.tool_registry.connected_mcp_servers),
        }
