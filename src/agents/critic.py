"""Critic Agent — reviews drafts, identifies gaps, and iterates until satisfied."""

from __future__ import annotations

import json

from src.agents.base import BaseAgent, AgentError
from config import MODEL_SONNET

_TOOL = {
    "name": "submit_critique",
    "description": "Submit the structured evaluation of the resume and cover letter drafts.",
    "input_schema": {
        "type": "object",
        "properties": {
            "resume_gaps": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Material gaps in the resume that would change the output if filled",
            },
            "cover_letter_gaps": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Material gaps in the cover letter",
            },
            "questions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Strategic gap-filling questions for the candidate (3-5 max). Empty list if no more questions worth asking.",
            },
            "alignment_score": {
                "type": "integer",
                "minimum": 1,
                "maximum": 10,
                "description": "Overall alignment score (1=major gaps, 10=fully optimized)",
            },
            "gap_assessment": {
                "type": "string",
                "description": "Summary of remaining gaps and their impact on the application. State clearly whether the gaps are material or acceptable.",
            },
            "accepts_as_final": {
                "type": "boolean",
                "description": "True when the drafts are strong enough to finalize and no more questions would materially improve the output.",
            },
        },
        "required": [
            "resume_gaps", "cover_letter_gaps", "questions",
            "alignment_score", "gap_assessment", "accepts_as_final",
        ],
    },
}


class CriticAgent(BaseAgent):
    name = "Critic"
    prompt_file = "critic.md"
    max_tokens = 2048
    model = MODEL_SONNET
    tools = [_TOOL]
    tool_choice = {"type": "tool", "name": "submit_critique"}
    needs_candidate_profile = True

    def run(self, state: dict) -> dict:
        analysis = state.get("analysis")
        strategy = state.get("strategy")
        draft_resume = state.get("draft_resume")
        draft_cover = state.get("draft_cover_letter")

        if not draft_resume or not draft_cover:
            raise AgentError(self.name, ValueError("Missing drafts in state"))

        already_asked = []
        mem = state.get("memory_json", {})
        if isinstance(mem, dict):
            already_asked = mem.get("questions_already_asked", [])

        sections = [
            f"## JOB ANALYSIS\n{json.dumps(analysis or {}, indent=2)}",
            f"## NARRATIVE STRATEGY\n{json.dumps(strategy or {}, indent=2)}",
            f"## DRAFT RESUME\n{draft_resume.get('text', '')}",
            f"## DRAFT COVER LETTER\n{draft_cover.get('text', '')}",
            f"## CANDIDATE RESUME MATERIALS\n{state.get('resume_content', '')}",
            f"## QUESTIONS ALREADY ASKED IN PRIOR RUNS (do NOT repeat these)\n"
            + "\n".join(f"- {q}" for q in already_asked),
        ]

        # Include accumulated answers from prior iterations
        if state.get("all_answers"):
            sections.append(
                f"## CANDIDATE'S ANSWERS FROM PRIOR ITERATIONS\n{state['all_answers']}"
            )

        # Authentic mode context
        if state.get("authentic_mode"):
            authentic_qs = (state.get("strategy") or {}).get("authentic_questions", [])
            pv = state.get("personal_voice_memory", {})
            auth_section = (
                "## AUTHENTIC VOICE MODE — ACTIVE\n"
                "This posting requests authentic, human-written content. "
                "See AUTHENTIC VOICE MODE in your instructions.\n"
            )
            if authentic_qs:
                auth_section += (
                    "\nStrategist's suggested personal questions to explore:\n"
                    + "\n".join(f"- {q}" for q in authentic_qs)
                )
            if pv:
                auth_section += f"\n\nKnown personal voice data from memory:\n{json.dumps(pv, indent=2)}"
            sections.append(auth_section)

        iteration = state.get("iteration_count", 0)
        if iteration > 0:
            sections.append(
                f"## ITERATION NOTE\n"
                f"This is iteration #{iteration + 1}. The drafts have already been refined "
                f"with the candidate's previous answers. Only ask NEW questions if their "
                f"answers would MATERIALLY improve the output. If the drafts are strong "
                f"enough, set accepts_as_final to true."
            )

        user_message = (
            "Review these drafts and submit your critique.\n\n"
            + "\n\n".join(sections)
        )

        response = self._call(user_message)
        critique = self.extract_tool_input(response, "submit_critique")
        state["critique"] = critique
        return state
