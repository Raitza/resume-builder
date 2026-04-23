"""Strategist Agent — crafts the narrative blueprint for an application."""

from __future__ import annotations

import json

from src.agents.base import BaseAgent, AgentError
from config import MODEL_OPUS

_TOOL = {
    "name": "submit_strategy",
    "description": "Submit the narrative strategy for this application.",
    "input_schema": {
        "type": "object",
        "properties": {
            "brand_angle": {
                "type": "string",
                "description": "One-sentence positioning statement for this application",
            },
            "story_arc": {
                "type": "string",
                "description": "Career narrative thread connecting past roles to this opportunity",
            },
            "experiences_to_highlight": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "role": {"type": "string"},
                        "framing_note": {"type": "string"},
                    },
                    "required": ["role", "framing_note"],
                },
                "description": "Ordered list of roles to feature with framing guidance",
            },
            "experiences_to_omit_or_minimize": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "role": {"type": "string"},
                        "reason": {"type": "string"},
                    },
                    "required": ["role", "reason"],
                },
                "description": "Roles to downplay and why",
            },
            "transition_framings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "from_to": {"type": "string"},
                        "framing": {"type": "string"},
                    },
                    "required": ["from_to", "framing"],
                },
                "description": "How to explain career pivots",
            },
            "tone_and_register": {
                "type": "string",
                "description": "Specific tone guidance for this application",
            },
            "opening_hook": {
                "type": "string",
                "description": "Suggested cover letter opening angle (not the text, the angle)",
            },
            "differentiators": {
                "type": "array",
                "items": {"type": "string"},
                "description": "2-3 things that make this candidate uniquely suited",
            },
            "section_order": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Resume section order that best serves the narrative (e.g. ['summary', 'experience', 'education', 'skills']). Lead with what makes the candidate strongest.",
            },
            "authentic_questions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "AUTHENTIC MODE ONLY: 2-3 deep personal questions to surface in the Critic phase — about values, personal connection to mission, or stories not in resume. Omit if authentic_mode is False.",
            },
        },
        "required": [
            "brand_angle", "story_arc", "experiences_to_highlight",
            "tone_and_register", "opening_hook", "differentiators",
            "section_order",
        ],
    },
}


class StrategistAgent(BaseAgent):
    name = "Strategist"
    prompt_file = "strategist.md"
    max_tokens = 2048
    model = MODEL_OPUS
    tools = [_TOOL]
    tool_choice = {"type": "tool", "name": "submit_strategy"}
    needs_candidate_profile = True

    def run(self, state: dict) -> dict:
        analysis = state.get("analysis")
        if not analysis:
            raise AgentError(self.name, ValueError("No analysis in state"))

        sections = [
            f"## JOB ANALYSIS\n{json.dumps(analysis, indent=2)}",
            f"## CANDIDATE RESUME MATERIALS\n{state.get('resume_content', '')}",
        ]
        if state.get("memory_json"):
            sections.append(
                f"## ACCUMULATED MEMORY\n{json.dumps(state['memory_json'], indent=2)}"
            )
        if state.get("memory_md"):
            sections.append(
                f"## SESSION NOTES & FEEDBACK\n{state['memory_md']}"
            )

        authentic_mode = state.get("authentic_mode", False)
        if authentic_mode:
            special = state.get("special_instructions", "")
            pv = state.get("personal_voice_memory", {})
            sections.append(
                "## AUTHENTIC VOICE MODE — ACTIVE\n"
                + (f"Special instructions from posting: {special}\n\n" if special else "")
                + "The posting explicitly requests authentic, human-written content. "
                "See the AUTHENTIC VOICE MODE section in your instructions.\n"
                + (f"Known personal voice data from memory:\n{json.dumps(pv, indent=2)}" if pv else "")
            )

        task = (
            "Create a narrative strategy for this application.\n\n"
            + ("IMPORTANT: authentic_mode=True — also populate authentic_questions.\n\n"
               if authentic_mode else "")
            + "\n\n".join(sections)
        )
        user_message = task

        response = self._call(user_message)
        strategy = self.extract_tool_input(response, "submit_strategy")
        state["strategy"] = strategy
        return state
