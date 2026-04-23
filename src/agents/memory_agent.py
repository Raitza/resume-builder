"""Memory Agent — decides what new facts to persist after an application cycle."""

from __future__ import annotations

import json

from src.agents.base import BaseAgent
from config import MODEL_HAIKU

_TOOL = {
    "name": "submit_memory_update",
    "description": "Submit the structured memory update with new facts to persist.",
    "input_schema": {
        "type": "object",
        "properties": {
            "updates": {
                "type": "object",
                "description": (
                    "New information to merge into memory.json. Use only these keys: "
                    "style_preferences, tone, recurring_fixes, "
                    "human_edits_patterns (patterns learned from comparing AI drafts vs the candidate's actual edited versions — ground-truth style rules), "
                    "candidate_facts (with sub-keys: achievements, experiences, context), "
                    "per_profile_type (with sub-keys: consulting, clean_energy, ngo_philanthropy), "
                    "personal_voice (with sub-keys: values, motivations, personal_stories, mission_connections — "
                    "only populate if authentic_mode was active and candidate shared personal insights). "
                    "Only include keys that have new information. Use empty object if nothing new."
                ),
            },
            "questions_asked": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Question IDs asked in this run (format: CompanyName_Role_Q1)",
            },
        },
        "required": ["updates", "questions_asked"],
    },
}


class MemoryAgent(BaseAgent):
    name = "Memory"
    prompt_file = "memory.md"
    max_tokens = 1024
    model = MODEL_HAIKU
    tools = [_TOOL]
    tool_choice = {"type": "tool", "name": "submit_memory_update"}
    needs_candidate_profile = False

    def run(self, state: dict) -> dict:
        analysis = state.get("analysis", {})
        company = analysis.get("company", "Unknown")
        role = analysis.get("role", "Unknown")

        sections = [
            f"## APPLICATION CONTEXT\nCompany: {company}\nRole: {role}",
            f"## CURRENT MEMORY\n{json.dumps(state.get('memory_json', {}), indent=2)}",
        ]

        # all_answers accumulates across all iteration rounds; user_answers is
        # just the latest round. Prefer all_answers so nothing is lost.
        all_qa = state.get("all_answers") or state.get("user_answers")
        if all_qa:
            sections.append(
                f"## CANDIDATE'S ANSWERS TO QUESTIONS (all rounds)\n{all_qa}"
            )
        else:
            sections.append("## CANDIDATE'S ANSWERS\n(No answers provided)")

        critique = state.get("critique", {})
        if critique.get("questions"):
            sections.append(
                "## QUESTIONS THAT WERE ASKED\n"
                + "\n".join(f"- {q}" for q in critique["questions"])
            )

        if state.get("authentic_mode"):
            pv = state.get("personal_voice_memory", {})
            auth_block = (
                "## AUTHENTIC VOICE MODE — ACTIVE\n"
                "See PERSONAL VOICE EXTRACTION in your instructions. "
                "Extract values, motivations, personal stories, and mission connections "
                "the candidate shared and save them to the personal_voice key.\n"
            )
            if pv:
                auth_block += f"Existing personal_voice data (do not duplicate):\n{json.dumps(pv, indent=2)}"
            sections.append(auth_block)

        user_message = (
            "Review this application cycle and submit any new facts to persist.\n\n"
            + "\n\n".join(sections)
        )

        response = self._call(user_message)
        result = self.extract_tool_input(response, "submit_memory_update")
        state["memory_update"] = {
            "updates": result.get("updates", {}),
            "questions_asked": result.get("questions_asked", []),
        }
        return state
