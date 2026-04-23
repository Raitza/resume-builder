"""Base agent class for all pipeline agents.

Provides:
- System prompt loading from src/agents/prompts/
- Claude Code subprocess calls (uses your Claude Code subscription, no API key needed)
- Structured JSON response parsing (replaces tool_use with prompt-based JSON output)
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import time
from typing import Any

_PROMPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts")
_RETRY_DELAYS = [10, 20, 40]  # seconds between retry attempts

logger = logging.getLogger(__name__)


class AgentError(Exception):
    """Raised when an agent fails during execution."""

    def __init__(self, agent_name: str, original_error: Exception):
        self.agent_name = agent_name
        self.original_error = original_error
        super().__init__(f"Agent '{agent_name}' failed: {original_error}")


def _load_prompt(filename: str) -> str:
    """Load a markdown prompt file from the prompts/ directory."""
    path = os.path.join(_PROMPTS_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# Shared candidate profile block — loaded once, reused by multiple agents.
_CANDIDATE_PROFILE: str | None = None


def get_candidate_profile() -> str:
    global _CANDIDATE_PROFILE
    if _CANDIDATE_PROFILE is None:
        _CANDIDATE_PROFILE = _load_prompt("_candidate_profile.md")
    return _CANDIDATE_PROFILE


def _tool_schema_to_json_instruction(tools: list[dict], tool_choice: dict | None) -> str:
    """Convert tool schemas into a plain-text instruction for JSON output.

    Instead of using the API's tool_use feature, we tell the model
    exactly what JSON structure to return.
    """
    if not tools:
        return ""

    # If a specific tool is forced, only show that schema
    if tool_choice and tool_choice.get("type") == "tool" and tool_choice.get("name"):
        target_name = tool_choice["name"]
        tools = [t for t in tools if t["name"] == target_name]

    parts = []
    for tool in tools:
        schema = tool.get("input_schema", {})
        properties = schema.get("properties", {})
        required = schema.get("required", [])

        # Build a readable description of each field
        fields = []
        for prop_name, prop_def in properties.items():
            prop_type = prop_def.get("type", "string")
            prop_desc = prop_def.get("description", "")
            req = " (REQUIRED)" if prop_name in required else ""
            fields.append(f'  "{prop_name}": {prop_type}{req} — {prop_desc}')

        parts.append(
            f"You MUST respond with ONLY a valid JSON object matching this schema.\n"
            f"Do NOT include any text before or after the JSON. No explanation, no markdown code fences.\n"
            f"JSON schema for '{tool['name']}':\n"
            + "{\n" + ",\n".join(fields) + "\n}"
        )

    return "\n\n".join(parts)


def _extract_json(text: str) -> dict:
    """Extract a JSON object from text, handling markdown code fences."""
    # Try direct parse first
    text = text.strip()
    if text.startswith("{"):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

    # Try extracting from markdown code fence
    match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Try finding the first { ... } block
    brace_start = text.find("{")
    if brace_start >= 0:
        # Find matching closing brace
        depth = 0
        for i in range(brace_start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[brace_start:i + 1])
                    except json.JSONDecodeError:
                        break

    raise ValueError(f"Could not extract JSON from response: {text[:200]}...")


class _ClaudeResponse:
    """Mimics the shape of anthropic.types.Message for backward compatibility.

    Agents use extract_tool_input(response, tool_name) and extract_text(response).
    This wrapper lets existing agent code work without changes.
    """

    def __init__(self, text: str, tool_name: str | None = None, parsed_json: dict | None = None):
        self._text = text
        self._tool_name = tool_name
        self._parsed_json = parsed_json
        self.content = []

        if parsed_json and tool_name:
            self.content.append(_ToolUseBlock(tool_name, parsed_json))
        if text:
            self.content.append(_TextBlock(text))


class _ToolUseBlock:
    type = "tool_use"

    def __init__(self, name: str, input_data: dict):
        self.name = name
        self.input = input_data


class _TextBlock:
    type = "text"

    def __init__(self, text: str):
        self.text = text


class BaseAgent:
    """Abstract base for every pipeline agent.

    Subclasses must set:
        name            – human-readable agent name (e.g. "Analyst")
        prompt_file     – filename in prompts/ (e.g. "analyst.md")
        max_tokens      – output token budget
        tools           – list of tool schemas, or None for plain-text output
        needs_candidate_profile – whether to append _candidate_profile.md

    And implement:
        run(state) -> state
    """

    name: str = "base"
    prompt_file: str = ""
    max_tokens: int = 2048
    model: str = ""  # overridden per subclass; empty = claude CLI default
    tools: list[dict] | None = None
    tool_choice: dict | None = None  # e.g. {"type": "tool", "name": "submit_analysis"}
    needs_candidate_profile: bool = False

    def __init__(self, model: str = ""):
        # Only override the class-level model if explicitly passed
        if model:
            self.model = model
        self._system_prompt: str | None = None

    @property
    def system_prompt(self) -> str:
        if self._system_prompt is None:
            prompt = _load_prompt(self.prompt_file) if self.prompt_file else ""
            if self.needs_candidate_profile:
                prompt = get_candidate_profile() + "\n\n" + prompt
            self._system_prompt = prompt
        return self._system_prompt

    def run(self, state: dict) -> dict:
        """Execute the agent. Reads from state, writes results back, returns state."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Claude Code subprocess call
    # ------------------------------------------------------------------

    def _call(
        self,
        user_message: str,
        *,
        tools: list[dict] | None = None,
        tool_choice: dict | None = None,
    ) -> _ClaudeResponse:
        """Call Claude via the 'claude' CLI subprocess.

        Uses your Claude Code subscription — no API key needed.

        Args:
            user_message: The user-role message content.
            tools: Override self.tools for this call (used for JSON schema instruction).
            tool_choice: Override self.tool_choice for this call.

        Returns:
            A _ClaudeResponse object compatible with extract_tool_input/extract_text.
        """
        resolved_tools = tools if tools is not None else self.tools
        resolved_choice = tool_choice if tool_choice is not None else self.tool_choice

        # Build the full prompt: system prompt + JSON schema instruction + user message
        json_instruction = _tool_schema_to_json_instruction(
            resolved_tools or [], resolved_choice
        )

        full_prompt = ""
        if self.system_prompt:
            full_prompt += self.system_prompt + "\n\n"
        if json_instruction:
            full_prompt += json_instruction + "\n\n"
        full_prompt += user_message

        # Determine the tool name for response parsing
        tool_name = None
        if resolved_choice and resolved_choice.get("type") == "tool":
            tool_name = resolved_choice.get("name")
        elif resolved_tools and len(resolved_tools) == 1:
            tool_name = resolved_tools[0]["name"]

        # Retry loop
        last_exc: Exception | None = None
        for attempt, delay in enumerate([0] + _RETRY_DELAYS):
            if delay:
                logger.info(
                    "[%s] Retrying in %ds (attempt %d)...",
                    self.name, delay, attempt + 1,
                )
                time.sleep(delay)

            try:
                cmd = ["claude", "-p", "-", "--output-format", "text"]
                if self.model:
                    cmd += ["--model", self.model]
                # Build a minimal environment for the subprocess so it always
                # authenticates with the user's own OAuth token (~/.claude/),
                # regardless of what the parent process (Streamlit/Claude Code) inherited.
                _KEEP_VARS = {
                    "PATH", "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA",
                    "TEMP", "TMP", "SYSTEMROOT", "SYSTEMDRIVE", "COMSPEC",
                    "USERNAME", "USERDOMAIN", "COMPUTERNAME",
                    "WINDIR", "OS", "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE",
                    "PROGRAMFILES", "PROGRAMFILES(X86)", "COMMONPROGRAMFILES",
                }
                clean_env = {k: v for k, v in os.environ.items()
                             if k.upper() in {v.upper() for v in _KEEP_VARS}}
                logger.info("[%s] clean_env keys: %s", self.name, sorted(clean_env.keys()))
                result = subprocess.run(
                    cmd,
                    input=full_prompt,
                    capture_output=True,
                    text=True,
                    timeout=300,  # 5 minute timeout per agent call
                    cwd=os.path.dirname(os.path.dirname(_PROMPTS_DIR)),  # project root
                    shell=True,  # Required on Windows to find .cmd files in PATH
                    encoding="utf-8",
                    errors="replace",
                    env=clean_env,
                )

                if result.returncode != 0:
                    error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
                    if "overloaded" in error_msg.lower() or "rate" in error_msg.lower():
                        last_exc = RuntimeError(f"Claude CLI error: {error_msg}")
                        continue
                    # Claude Pro message rate limit — retrying won't help, surface clearly
                    if "hit your limit" in error_msg.lower() or "resets" in error_msg.lower():
                        raise RuntimeError(
                            f"⏳ Claude Pro message limit reached. {error_msg}. "
                            f"Wait until the reset time shown above, then try again."
                        )
                    raise RuntimeError(f"Claude CLI failed (exit {result.returncode}): {error_msg}")

                response_text = result.stdout.strip()
                if not response_text:
                    raise RuntimeError("Claude CLI returned empty response")

                # If we expect structured JSON, parse it
                if tool_name and resolved_tools:
                    parsed = _extract_json(response_text)
                    return _ClaudeResponse(
                        text=response_text,
                        tool_name=tool_name,
                        parsed_json=parsed,
                    )
                else:
                    return _ClaudeResponse(text=response_text)

            except subprocess.TimeoutExpired:
                last_exc = RuntimeError(f"Claude CLI timed out after 300s")
                continue
            except json.JSONDecodeError as exc:
                last_exc = exc
                continue
            except RuntimeError as exc:
                if "overloaded" in str(exc).lower():
                    last_exc = exc
                    continue
                raise

        raise AgentError(self.name, last_exc or RuntimeError("All retries exhausted"))

    # ------------------------------------------------------------------
    # Response parsing helpers (backward-compatible with existing agents)
    # ------------------------------------------------------------------

    @staticmethod
    def extract_tool_input(response: _ClaudeResponse, tool_name: str) -> dict:
        """Extract the input dict from a tool_use content block matching *tool_name*."""
        for block in response.content:
            if block.type == "tool_use" and block.name == tool_name:
                return block.input
        raise ValueError(
            f"No tool_use block named '{tool_name}' in response. "
            f"Blocks: {[b.type for b in response.content]}"
        )

    @staticmethod
    def extract_text(response: _ClaudeResponse) -> str:
        """Extract plain text from a response (first text block)."""
        for block in response.content:
            if block.type == "text":
                return block.text
        return ""
