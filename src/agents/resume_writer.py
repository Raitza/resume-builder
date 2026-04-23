"""Resume Writer Agent — produces a resume following the Strategist's blueprint."""

from __future__ import annotations

import json

from src.agents.base import BaseAgent, AgentError
from config import MODEL_OPUS

_TOOL = {
    "name": "submit_resume",
    "description": "Submit the completed resume.",
    "input_schema": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The full resume text, ready for formatting",
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


class ResumeWriterAgent(BaseAgent):
    name = "Resume Writer"
    prompt_file = "resume_writer.md"
    max_tokens = 4096
    model = MODEL_OPUS
    tools = [_TOOL]
    tool_choice = {"type": "tool", "name": "submit_resume"}
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
        # Section order comes from the Strategist (storytelling decision)
        strategy = state.get("strategy", {})
        if strategy.get("section_order"):
            sections.append(
                f"## SECTION ORDER (from narrative strategy)\n"
                f"Arrange resume sections in this order: {', '.join(strategy['section_order'])}\n"
                f"This order was chosen to best serve the candidate's narrative for this role."
            )

        layout = state.get("layout")
        if layout:
            # Give the writer the visual/spacing constraints so it writes to fit
            layout_summary = []
            if layout.get("page_count_target"):
                layout_summary.append(
                    f"- Page count target: {layout['page_count_target']} page(s) — HARD CONSTRAINT"
                )
            if layout.get("font_family"):
                layout_summary.append(f"- Font: {layout['font_family']}")
            if layout.get("body_pt"):
                layout_summary.append(f"- Body font size: {layout['body_pt']}pt")
            if layout.get("line_spacing_pt"):
                layout_summary.append(f"- Line spacing: {layout['line_spacing_pt']}pt")
            if layout.get("top_margin") and layout.get("bottom_margin"):
                usable_height = 11.0 - layout["top_margin"] - layout["bottom_margin"]
                lines_per_page = int((usable_height * 72) / layout.get("line_spacing_pt", 13))
                page_target = layout.get("page_count_target", 2)
                total_lines = lines_per_page * page_target
                layout_summary.append(
                    f"- Estimated capacity: ~{lines_per_page} lines/page, "
                    f"~{total_lines} lines total for {page_target} page(s)"
                )
            for key in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
                if layout.get(key):
                    layout_summary.append(f"- {key}: {layout[key]}\"")
            if layout.get("header_style"):
                layout_summary.append(f"- Header style: {layout['header_style']}")
            if layout.get("design_rationale"):
                layout_summary.append(f"- Design rationale: {layout['design_rationale']}")

            sections.append(
                "## LAYOUT DESIGN SPECIFICATION\n"
                "Write content that fits within these design constraints:\n"
                + "\n".join(layout_summary)
            )
        return "\n\n".join(sections)

    def run(self, state: dict) -> dict:
        if not state.get("strategy"):
            raise AgentError(self.name, ValueError("No strategy in state"))

        context = self._build_context(state)
        response = self._call(
            f"Write the first draft of the resume.\n\n{context}"
        )

        result = self.extract_tool_input(response, "submit_resume")
        state["draft_resume"] = {
            "text": result.get("text", ""),
            "assumptions_made": result.get("assumptions_made", []),
        }
        return state

    def run_refinement(self, state: dict) -> dict:
        context = self._build_context(state)

        extras = []
        critique = state.get("critique")
        if critique and critique.get("resume_gaps"):
            extras.append(
                "## GAPS IDENTIFIED BY REVIEWER\n"
                + "\n".join(f"- {g}" for g in critique["resume_gaps"])
            )
        # Include all accumulated answers from iterations
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
            "Produce the FINAL version of the resume incorporating the candidate's answers "
            "and addressing the reviewer's gaps.\n\n"
            + context + "\n\n" + "\n\n".join(extras)
        )

        response = self._call(user_message)
        result = self.extract_tool_input(response, "submit_resume")
        state["final_resume"] = {
            "text": result.get("text", ""),
            "assumptions_made": result.get("assumptions_made", []),
        }
        return state
