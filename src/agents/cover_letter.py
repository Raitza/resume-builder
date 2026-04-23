"""Cover Letter Agent — produces a cover letter following the Strategist's blueprint."""

from __future__ import annotations

import json

from src.agents.base import BaseAgent, AgentError
from config import MODEL_OPUS

_TOOL = {
    "name": "submit_cover_letter",
    "description": "Submit the completed cover letter.",
    "input_schema": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The full cover letter text",
            },
            "assumptions_made": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Assumptions made due to missing information",
            },
        },
        "required": ["text"],
    },
}


class CoverLetterAgent(BaseAgent):
    name = "Cover Letter Writer"
    prompt_file = "cover_letter.md"
    max_tokens = 2048
    model = MODEL_OPUS
    tools = [_TOOL]
    tool_choice = {"type": "tool", "name": "submit_cover_letter"}
    needs_candidate_profile = True

    def _build_context(self, state: dict) -> str:
        sections = [
            f"## JOB ANALYSIS\n{json.dumps(state.get('analysis', {}), indent=2)}",
            f"## NARRATIVE STRATEGY\n{json.dumps(state.get('strategy', {}), indent=2)}",
            f"## CANDIDATE RESUME MATERIALS\n{state.get('resume_content', '')}",
        ]
        if state.get("memory_json"):
            sections.append(
                f"## ACCUMULATED MEMORY\n{json.dumps(state['memory_json'], indent=2)}"
            )
        if state.get("memory_md"):
            sections.append(f"## SESSION NOTES\n{state['memory_md']}")
        layout = state.get("layout")
        if layout:
            layout_summary = []
            if layout.get("font_family"):
                layout_summary.append(f"- Font: {layout['font_family']}")
            if layout.get("body_pt"):
                layout_summary.append(f"- Body font size: {layout['body_pt']}pt")
            if layout.get("line_spacing_pt"):
                layout_summary.append(f"- Line spacing: {layout['line_spacing_pt']}pt")
            if layout.get("top_margin") and layout.get("bottom_margin"):
                usable_height = 11.0 - layout["top_margin"] - layout["bottom_margin"]
                lines_per_page = int((usable_height * 72) / layout.get("line_spacing_pt", 13))
                layout_summary.append(
                    f"- Estimated capacity: ~{lines_per_page} lines on 1 page"
                )
            if layout.get("design_rationale"):
                layout_summary.append(f"- Design rationale: {layout['design_rationale']}")
            sections.append(
                "## LAYOUT DESIGN SPECIFICATION\n"
                "Write content that fits within 1 page given these constraints:\n"
                + "\n".join(layout_summary)
            )
        if state.get("authentic_mode"):
            special = state.get("special_instructions", "")
            pv = state.get("personal_voice_memory", {})
            auth_block = (
                "## AUTHENTIC VOICE MODE — ACTIVE\n"
                "See AUTHENTIC VOICE MODE in your instructions.\n"
            )
            if special:
                auth_block += f"Posting instruction: {special}\n"
            if pv:
                auth_block += f"\nKnown personal voice data (values, stories, motivations):\n{json.dumps(pv, indent=2)}"
            sections.append(auth_block)
        return "\n\n".join(sections)

    def run(self, state: dict) -> dict:
        if not state.get("strategy"):
            raise AgentError(self.name, ValueError("No strategy in state"))

        context = self._build_context(state)
        response = self._call(
            f"Write the first draft of the cover letter.\n\n{context}"
        )

        result = self.extract_tool_input(response, "submit_cover_letter")
        state["draft_cover_letter"] = {
            "text": result.get("text", ""),
            "assumptions_made": result.get("assumptions_made", []),
        }
        return state

    def run_refinement(self, state: dict) -> dict:
        context = self._build_context(state)

        extras = []
        critique = state.get("critique")
        if critique and critique.get("cover_letter_gaps"):
            extras.append(
                "## GAPS IDENTIFIED BY REVIEWER\n"
                + "\n".join(f"- {g}" for g in critique["cover_letter_gaps"])
            )
        if state.get("all_answers"):
            extras.append(
                f"## ALL CANDIDATE ANSWERS (accumulated across iterations)\n{state['all_answers']}"
            )
        elif state.get("user_answers"):
            extras.append(
                f"## CANDIDATE'S ANSWERS TO QUESTIONS\n{state['user_answers']}"
            )
        if state.get("user_feedback"):
            extras.append(
                f"## USER FEEDBACK ON PREVIOUS OUTPUT\n{state['user_feedback']}\n"
                "Address this feedback in the revised version."
            )

        user_message = (
            "Produce the FINAL version of the cover letter incorporating the candidate's "
            "answers and addressing the reviewer's gaps.\n\n"
            + context + "\n\n" + "\n\n".join(extras)
        )

        response = self._call(user_message)
        result = self.extract_tool_input(response, "submit_cover_letter")
        state["final_cover_letter"] = {
            "text": result.get("text", ""),
            "assumptions_made": result.get("assumptions_made", []),
        }
        return state
