from exorous.tools.builtin.edit_file import EditTool
from exorous.tools.builtin.glob import GlobTool
from exorous.tools.builtin.grep import GrepTool
from exorous.tools.builtin.list_dir import ListDirTool
from exorous.tools.builtin.memory import MemoryTool
from exorous.tools.builtin.read_file import ReadFileTool
from exorous.tools.builtin.shell import ShellTool
from exorous.tools.builtin.todo import TodosTool
from exorous.tools.builtin.web_fetch import WebFetchTool
from exorous.tools.builtin.web_search import WebSearchTool
from exorous.tools.builtin.write_file import WriteFileTool

__all__ = [
    "ReadFileTool",
    "WriteFileTool",
    "EditTool",
    "ShellTool",
    "ListDirTool",
    "GrepTool",
    "GlobTool",
    "WebSearchTool",
    "WebFetchTool",
    "TodosTool",
    "MemoryTool",
]


def get_all_builtin_tools() -> list[type]:
    return [
        ReadFileTool,
        WriteFileTool,
        EditTool,
        ShellTool,
        ListDirTool,
        GrepTool,
        GlobTool,
        WebSearchTool,
        WebFetchTool,
        TodosTool,
        MemoryTool,
    ]
