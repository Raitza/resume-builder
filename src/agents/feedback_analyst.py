"""Feedback Analyst — compares Claude's output vs user-edited versions to extract style learnings."""

from __future__ import annotations

import json

from src.agents.base import BaseAgent
from config import MODEL_SONNET


class FeedbackAnalyst(BaseAgent):
    name = "FeedbackAnalyst"
    prompt_file = "feedback_analyst.md"
    max_tokens = 2048
    model = MODEL_SONNET
    tools = None  # plain JSON output (schema embedded in system prompt)
    tool_choice = None
    needs_candidate_profile = False

    def run(self, state: dict) -> dict:
        """Analyze paired feedback/output files and return style learnings.

        Expects state to contain:
            "feedback_pairs": list of dicts from feedback_reader.pair_feedback_with_output()
            "already_analyzed": list of filenames already processed in previous runs
        """
        pairs = state.get("feedback_pairs", [])
        already_analyzed = state.get("already_analyzed", [])

        # Filter to only new pairs (not yet analyzed)
        new_pairs = [
            p for p in pairs
            if p.get("company_tag") not in already_analyzed
            # More precise: check by company_tag+type combination
        ]

        if not new_pairs:
            state["feedback_learnings"] = {}
            return state

        from src.agents.base import _extract_json

        # Process one pair at a time to avoid oversized prompts
        merged: dict[str, list] = {
            "human_edits_patterns": [],
            "style_preferences": [],
            "recurring_fixes": [],
        }

        for pair in new_pairs:
            tag = pair["company_tag"] or "unknown"
            doc_type = pair["type"]
            folder = pair["folder"]
            claude_out = pair["claude_output"]
            user_edited = pair["user_edited"]

            lines = [f"## DOCUMENT: {doc_type.replace('_', ' ').title()} — {tag}\n"]
            if claude_out:
                lines.append(f"**CLAUDE'S ORIGINAL OUTPUT:**\n{claude_out.strip()}\n")
            else:
                lines.append("**CLAUDE'S ORIGINAL OUTPUT:** (not found — analyze user's version for style patterns only)\n")
            lines.append(f"**USER'S EDITED VERSION:**\n{user_edited.strip()}\n")

            user_message = "Analyze this document pair and extract style learnings.\n\n" + "\n".join(lines)

            try:
                response = self._call(user_message)
                raw_text = response._text.strip()
                result = _extract_json(raw_text)
                for key in ("human_edits_patterns", "style_preferences", "recurring_fixes"):
                    for item in result.get(key, []):
                        if item not in merged[key]:
                            merged[key].append(item)
            except Exception:
                continue  # skip failed pair, don't abort entire run

        state["feedback_learnings"] = merged
        return state
