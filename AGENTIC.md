# Agentic AI Architecture for Ghostline

## Overview

Replace the current pre-gathered context approach with an agentic tool-based system where the AI decides what information it needs and can perform actions like reading/writing files.

### Current Flow (Pre-gathered Context)
```
User message
    ↓
Context engine gathers files (keyword search, symbols, recent files)
    ↓
Send prompt + all context to AI
    ↓
AI responds
```

### New Flow (Agentic)
```
User message
    ↓
Send prompt + tool definitions to AI
    ↓
AI decides: needs context? → calls read_file, search_code, etc.
    ↓
Tool results fed back to AI
    ↓
AI decides: needs to act? → calls write_file, create_folder, etc.
    ↓
AI responds with summary
```

---

## Tool Definitions

### Read Tools
| Tool | Description | Parameters |
|------|-------------|------------|
| `read_file` | Read contents of a file | `path: str` |
| `search_code` | Search for text/regex in codebase | `query: str, regex: bool, file_pattern: str?` |
| `search_symbols` | Find functions/classes by name | `name: str, kind: "function"\|"class"\|"all"` |
| `list_directory` | List files in a directory | `path: str, recursive: bool` |
| `get_file_info` | Get metadata about a file | `path: str` |

### Write Tools
| Tool | Description | Parameters |
|------|-------------|------------|
| `write_file` | Create or overwrite a file | `path: str, content: str` |
| `edit_file` | Apply targeted edits to a file | `path: str, edits: [{old: str, new: str}]` |
| `create_directory` | Create a new folder | `path: str` |
| `delete_file` | Delete a file (with confirmation) | `path: str` |
| `rename_file` | Rename/move a file | `old_path: str, new_path: str` |

### Execution Tools
| Tool | Description | Parameters |
|------|-------------|------------|
| `run_command` | Run a shell command | `command: str, cwd: str?` |
| `run_python` | Execute Python code | `code: str` |

---

## Provider-Specific Implementation

### Claude (Anthropic)

Claude has native tool use support via the `tools` parameter.

```python
import anthropic

client = anthropic.Anthropic()

tools = [
    {
        "name": "read_file",
        "description": "Read the contents of a file at the given path",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute or relative path to the file"
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "write_file",
        "description": "Write content to a file, creating it if it doesn't exist",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"}
            },
            "required": ["path", "content"]
        }
    },
    # ... more tools
]

response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    tools=tools,
    messages=[{"role": "user", "content": user_message}]
)

# Handle tool use
if response.stop_reason == "tool_use":
    tool_use = response.content[0]  # Get tool call
    tool_name = tool_use.name
    tool_input = tool_use.input

    # Execute tool and get result
    result = execute_tool(tool_name, tool_input)

    # Send result back to Claude
    messages.append({"role": "assistant", "content": response.content})
    messages.append({
        "role": "user",
        "content": [{
            "type": "tool_result",
            "tool_use_id": tool_use.id,
            "content": result
        }]
    })
    # Continue conversation...
```

### OpenAI

OpenAI uses `functions` or `tools` parameter (newer API).

```python
from openai import OpenAI

client = OpenAI()

tools = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file at the given path",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file"
                    }
                },
                "required": ["path"]
            }
        }
    },
    # ... more tools
]

response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": user_message}],
    tools=tools,
    tool_choice="auto"
)

message = response.choices[0].message

if message.tool_calls:
    for tool_call in message.tool_calls:
        tool_name = tool_call.function.name
        tool_args = json.loads(tool_call.function.arguments)

        result = execute_tool(tool_name, tool_args)

        messages.append(message)
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": result
        })
    # Continue conversation...
```

### Ollama

Ollama supports tool calling for compatible models (llama3.1+, mistral, etc.).

```python
import ollama

tools = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"}
                },
                "required": ["path"]
            }
        }
    },
    # ... more tools
]

response = ollama.chat(
    model="llama3.1",
    messages=[{"role": "user", "content": user_message}],
    tools=tools
)

if response["message"].get("tool_calls"):
    for tool_call in response["message"]["tool_calls"]:
        tool_name = tool_call["function"]["name"]
        tool_args = tool_call["function"]["arguments"]

        result = execute_tool(tool_name, tool_args)

        messages.append(response["message"])
        messages.append({
            "role": "tool",
            "content": result
        })
    # Continue conversation...
```

**Note:** Not all Ollama models support tool calling. Need to check model capabilities.

---

## Unified Tool Executor

Create a provider-agnostic tool execution layer:

```python
# ghostline/ai/tools/executor.py

from pathlib import Path
from typing import Any
import subprocess

class ToolExecutor:
    """Execute tools requested by AI agents."""

    def __init__(self, workspace_root: Path):
        self.workspace = workspace_root
        self.allowed_tools = {
            "read_file": self.read_file,
            "write_file": self.write_file,
            "edit_file": self.edit_file,
            "search_code": self.search_code,
            "list_directory": self.list_directory,
            "create_directory": self.create_directory,
            "run_command": self.run_command,
        }

    def execute(self, tool_name: str, args: dict[str, Any]) -> str:
        """Execute a tool and return the result as a string."""
        if tool_name not in self.allowed_tools:
            return f"Error: Unknown tool '{tool_name}'"

        try:
            return self.allowed_tools[tool_name](**args)
        except Exception as e:
            return f"Error executing {tool_name}: {e}"

    def read_file(self, path: str) -> str:
        """Read file contents."""
        full_path = self._resolve_path(path)
        if not full_path.exists():
            return f"Error: File not found: {path}"
        if not full_path.is_file():
            return f"Error: Not a file: {path}"
        return full_path.read_text()

    def write_file(self, path: str, content: str) -> str:
        """Write content to file."""
        full_path = self._resolve_path(path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)
        return f"Successfully wrote {len(content)} bytes to {path}"

    def edit_file(self, path: str, edits: list[dict]) -> str:
        """Apply search-replace edits to a file."""
        full_path = self._resolve_path(path)
        if not full_path.exists():
            return f"Error: File not found: {path}"

        content = full_path.read_text()
        for edit in edits:
            old, new = edit["old"], edit["new"]
            if old not in content:
                return f"Error: Could not find text to replace: {old[:50]}..."
            content = content.replace(old, new, 1)

        full_path.write_text(content)
        return f"Successfully applied {len(edits)} edit(s) to {path}"

    def search_code(self, query: str, regex: bool = False, file_pattern: str = None) -> str:
        """Search for code in the workspace."""
        # Use ripgrep or fallback to grep
        cmd = ["rg", "--json", "-n"]
        if not regex:
            cmd.append("-F")  # Fixed string
        if file_pattern:
            cmd.extend(["-g", file_pattern])
        cmd.extend([query, str(self.workspace)])

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        # Parse and format results...
        return result.stdout[:4000]  # Truncate for token limits

    def list_directory(self, path: str = ".", recursive: bool = False) -> str:
        """List directory contents."""
        full_path = self._resolve_path(path)
        if not full_path.is_dir():
            return f"Error: Not a directory: {path}"

        if recursive:
            files = list(full_path.rglob("*"))[:100]  # Limit results
        else:
            files = list(full_path.iterdir())

        return "\n".join(str(f.relative_to(self.workspace)) for f in files)

    def create_directory(self, path: str) -> str:
        """Create a directory."""
        full_path = self._resolve_path(path)
        full_path.mkdir(parents=True, exist_ok=True)
        return f"Created directory: {path}"

    def run_command(self, command: str, cwd: str = None) -> str:
        """Run a shell command."""
        work_dir = self._resolve_path(cwd) if cwd else self.workspace
        result = subprocess.run(
            command,
            shell=True,
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=60
        )
        output = result.stdout + result.stderr
        return output[:4000]  # Truncate

    def _resolve_path(self, path: str) -> Path:
        """Resolve path relative to workspace."""
        p = Path(path)
        if p.is_absolute():
            return p
        return self.workspace / p
```

---

## Agentic Loop

The core loop that handles multi-turn tool calling:

```python
# ghostline/ai/agentic_client.py

from typing import Generator
from ghostline.ai.tools.executor import ToolExecutor
from ghostline.ai.tools.definitions import get_tool_definitions

class AgenticClient:
    """Provider-agnostic agentic AI client."""

    MAX_TOOL_ROUNDS = 10  # Prevent infinite loops

    def __init__(self, provider: str, model: str, workspace: Path):
        self.provider = provider
        self.model = model
        self.executor = ToolExecutor(workspace)
        self.tools = get_tool_definitions(provider)  # Format for provider

    def chat(
        self,
        messages: list[dict],
        stream: bool = True
    ) -> Generator[AgentEvent, None, None]:
        """
        Run agentic chat loop.

        Yields events:
        - TextDelta(text): Streaming text from AI
        - ToolCall(name, args): AI is calling a tool
        - ToolResult(name, result): Tool execution result
        - Done(full_response): Conversation complete
        """
        rounds = 0

        while rounds < self.MAX_TOOL_ROUNDS:
            rounds += 1

            # Call the AI
            response = self._call_provider(messages, stream=stream)

            # Stream text deltas
            for event in response:
                if isinstance(event, TextDelta):
                    yield event

            # Check for tool calls
            tool_calls = self._extract_tool_calls(response)

            if not tool_calls:
                # No tool calls, we're done
                yield Done(self._get_final_text(response))
                return

            # Execute tools and add results to messages
            for tool_call in tool_calls:
                yield ToolCall(tool_call.name, tool_call.args)

                result = self.executor.execute(tool_call.name, tool_call.args)

                yield ToolResult(tool_call.name, result)

                # Add to messages for next round
                self._append_tool_result(messages, tool_call, result)

        yield Done("Max tool rounds reached")

    def _call_provider(self, messages, stream):
        """Call the appropriate provider."""
        if self.provider == "anthropic":
            return self._call_anthropic(messages, stream)
        elif self.provider == "openai":
            return self._call_openai(messages, stream)
        elif self.provider == "ollama":
            return self._call_ollama(messages, stream)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    # Provider-specific implementations...
```

---

## UI Integration

### Tool Call Visualization

Show tool calls in the chat UI:

```
┌─────────────────────────────────────────────┐
│ You                                         │
│ Can you add error handling to the login     │
│ function?                                   │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ AI                                          │
│ ┌─────────────────────────────────────────┐ │
│ │ 🔍 read_file("src/auth/login.py")       │ │
│ └─────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────┐ │
│ │ ✏️  edit_file("src/auth/login.py")       │ │
│ │    +3 lines, -1 line                    │ │
│ └─────────────────────────────────────────┘ │
│                                             │
│ I've added try/except error handling to     │
│ the login function. The changes include...  │
└─────────────────────────────────────────────┘
```

### Approval Mode

Optional setting to require user approval before write operations:

```python
class ApprovalMode(Enum):
    AUTO = "auto"           # Execute all tools automatically
    WRITE_APPROVAL = "write"  # Approve write operations only
    ALL_APPROVAL = "all"    # Approve all tool calls
```

---

## File Structure

```
ghostline/ai/
├── __init__.py
├── ai_client.py          # Keep for backward compat
├── agentic_client.py     # New agentic client
├── tools/
│   ├── __init__.py
│   ├── definitions.py    # Tool schemas for each provider
│   ├── executor.py       # Tool execution
│   └── sandbox.py        # Optional sandboxing for commands
├── providers/
│   ├── __init__.py
│   ├── anthropic.py      # Claude-specific handling
│   ├── openai.py         # OpenAI-specific handling
│   └── ollama.py         # Ollama-specific handling
└── events.py             # Event types (TextDelta, ToolCall, etc.)
```

---

## Migration Path

### Phase 1: Add Tool Infrastructure
- [ ] Create tool definitions module
- [ ] Create tool executor
- [ ] Add provider-specific tool formatting

### Phase 2: Implement Agentic Client
- [ ] Create agentic loop
- [ ] Add event streaming
- [ ] Implement for Claude first (best tool support)
- [ ] Add OpenAI support
- [ ] Add Ollama support (with capability detection)

### Phase 3: UI Updates
- [ ] Add tool call visualization to chat bubbles
- [ ] Add approval mode UI
- [ ] Show file diffs for write operations
- [ ] Add "undo" for file changes

### Phase 4: Polish
- [ ] Add tool call history/logging
- [ ] Implement sandboxing for run_command
- [ ] Add rate limiting / token budgets
- [ ] Remove old context engine (or keep as fallback for non-tool models)

---

## Security Considerations

1. **Path Traversal**: Validate all paths are within workspace
2. **Command Injection**: Sanitize or sandbox shell commands
3. **Token Limits**: Truncate large file reads
4. **Write Confirmation**: Optional approval for destructive operations
5. **Sensitive Files**: Block reading .env, credentials, etc.

---

## Model Compatibility

| Provider | Models with Tool Support |
|----------|-------------------------|
| Anthropic | Claude 3+ (all variants) |
| OpenAI | GPT-4, GPT-4 Turbo, GPT-3.5 Turbo |
| Ollama | llama3.1+, mistral-nemo, command-r+ |

Models without tool support will fall back to the current context-injection approach.
