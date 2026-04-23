"""Layout Designer Agent — decides visual design parameters for the application."""

from __future__ import annotations

import json

from src.agents.base import BaseAgent, AgentError
from config import MODEL_SONNET

_TOOL = {
    "name": "submit_layout",
    "description": "Submit the document design specification.",
    "input_schema": {
        "type": "object",
        "properties": {
            "font_family": {
                "type": "string",
                "enum": ["Calibri", "Garamond", "Arial", "Cambria"],
                "description": "ATS-safe font family",
            },
            "body_pt": {"type": "number", "description": "Body text font size in points"},
            "header_name_pt": {"type": "number", "description": "Candidate name header font size"},
            "section_heading_pt": {"type": "number", "description": "Section heading font size"},
            "top_margin": {"type": "number", "description": "Top margin in inches"},
            "bottom_margin": {"type": "number", "description": "Bottom margin in inches"},
            "left_margin": {"type": "number", "description": "Left margin in inches"},
            "right_margin": {"type": "number", "description": "Right margin in inches"},
            "line_spacing_pt": {"type": "number", "description": "Line spacing in points"},
            "space_after_pt": {"type": "number", "description": "Paragraph spacing after in points"},
            "bullet_indent": {"type": "number", "description": "Bullet indent in inches"},
            "heading_space_before_pt": {"type": "number", "description": "Space before section headings in points"},
            "page_count_target": {
                "type": "integer",
                "enum": [1, 2],
                "description": "Target page count",
            },
            "header_style": {
                "type": "string",
                "enum": ["minimal", "centered", "left-aligned"],
                "description": "Document header layout style",
            },
            "design_rationale": {
                "type": "string",
                "description": "Brief explanation of why these choices fit this application",
            },
            "accent_color": {
                "type": "string",
                "description": "Hex color for section headings and dividers (e.g. '#2B579A' for navy)",
            },
            "heading_underline": {
                "type": "boolean",
                "description": "Whether section headings have a colored underline",
            },
            "name_color": {
                "type": "string",
                "description": "Hex color for candidate name in header (e.g. '#1A1A1A' for near-black)",
            },
            "divider_style": {
                "type": "string",
                "enum": ["solid_line", "double_line", "none"],
                "description": "Style of divider between sections",
            },
            "contact_style": {
                "type": "string",
                "enum": ["pipe_separated", "bullet_separated", "stacked"],
                "description": "How contact info is formatted",
            },
        },
        "required": [
            "font_family", "body_pt", "header_name_pt", "section_heading_pt",
            "top_margin", "bottom_margin", "left_margin", "right_margin",
            "line_spacing_pt", "space_after_pt", "bullet_indent",
            "heading_space_before_pt", "page_count_target",
            "header_style", "design_rationale",
            "accent_color", "heading_underline", "name_color", "divider_style",
        ],
    },
}


class LayoutDesignerAgent(BaseAgent):
    name = "Layout Designer"
    prompt_file = "layout_designer.md"
    max_tokens = 1024
    model = MODEL_SONNET
    tools = [_TOOL]
    tool_choice = {"type": "tool", "name": "submit_layout"}
    needs_candidate_profile = False

    def run(self, state: dict) -> dict:
        analysis = state.get("analysis")
        if not analysis:
            raise AgentError(self.name, ValueError("No analysis in state"))

        sections = [
            f"## JOB ANALYSIS\n{json.dumps(analysis, indent=2)}",
        ]
        strategy = state.get("strategy")
        if strategy:
            sections.append(
                f"## NARRATIVE STRATEGY (for tone context)\n"
                f"Tone: {strategy.get('tone_and_register', 'N/A')}\n"
                f"Brand angle: {strategy.get('brand_angle', 'N/A')}"
            )

        user_message = (
            "Design the document layout for this application.\n\n"
            + "\n\n".join(sections)
        )

        response = self._call(user_message)
        layout = self.extract_tool_input(response, "submit_layout")
        state["layout"] = layout
        return state
