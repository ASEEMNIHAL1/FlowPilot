from dataclasses import dataclass, field
from typing import Any, Callable

from pydantic import BaseModel, ValidationError


class ToolError(Exception):
    def __init__(self, message: str, code: str = "tool_error"):
        super().__init__(message)
        self.code = code


@dataclass
class Tool:
    name: str
    description: str
    args_model: type[BaseModel]
    handler: Callable[..., dict]
    permissions: str = "read"


@dataclass
class ToolContext:
    db: Any
    settings: Any
    run_id: int | None = None
    inject_create_failures: int = 0
    _failure_remaining: int = field(default=0)


def openai_schema(tool: Tool) -> dict:
    schema = tool.args_model.model_json_schema()
    schema.pop("title", None)
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": schema,
        },
    }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise ToolError(f"Unknown tool '{name}'", "unknown_tool")
        return self._tools[name]

    def schemas(self) -> list[dict]:
        return [openai_schema(tool) for tool in self._tools.values()]

    def execute(self, name: str, raw_args: dict, ctx: ToolContext) -> dict:
        tool = self.get(name)
        try:
            args = tool.args_model.model_validate(raw_args or {})
        except ValidationError as exc:
            raise ToolError(f"Invalid arguments for {name}: {exc.errors()}", "invalid_args") from exc
        return tool.handler(ctx=ctx, **args.model_dump())
