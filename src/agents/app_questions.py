"""Application Questions Agent — drafts answers to job application essay prompts."""

from __future__ import annotations

import json

from src.agents.base import BaseAgent, AgentError
from config import MODEL_OPUS

_TOOL = {
    "name": "submit_answers",
    "description": "Submit drafted answers to application questions.",
    "input_schema": {
        "type": "object",
        "properties": {
            "answers": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question": {
                            "type": "string",
                            "description": "The original application question",
                        },
                        "answer": {
                            "type": "string",
                            "description": "The drafted answer",
                        },
                        "word_count": {
                            "type": "integer",
                            "description": "Word count of the answer",
                        },
                        "assumptions_made": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Assumptions made due to missing information",
                        },
                    },
                    "required": ["question", "answer"],
                },
                "description": "One drafted answer per application question",
            },
            "clarifying_questions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Questions for the candidate if more info is needed to write strong answers. Empty if none needed.",
            },
        },
        "required": ["answers", "clarifying_questions"],
    },
}


class AppQuestionsAgent(BaseAgent):
    name = "Application Questions"
    prompt_file = "app_questions.md"
    max_tokens = 4096
    model = MODEL_OPUS
    tools = [_TOOL]
    tool_choice = {"type": "tool", "name": "submit_answers"}
    needs_candidate_profile = True

    def run(self, state: dict) -> dict:
        app_questions = state.get("application_questions", "")
        if not app_questions:
            raise AgentError(self.name, ValueError("No application_questions in state"))

        analysis = state.get("analysis", {})
        strategy = state.get("strategy", {})

        sections = [
            f"## JOB ANALYSIS\n{json.dumps(analysis, indent=2)}",
            f"## NARRATIVE STRATEGY\n{json.dumps(strategy, indent=2)}",
            f"## CANDIDATE RESUME MATERIALS\n{state.get('resume_content', '')}",
        ]
        if state.get("memory_json"):
            sections.append(
                f"## ACCUMULATED MEMORY\n{json.dumps(state['memory_json'], indent=2)}"
            )
        if state.get("memory_md"):
            sections.append(f"## SESSION NOTES\n{state['memory_md']}")

        sections.append(
            f"## APPLICATION QUESTIONS TO ANSWER\n{app_questions}"
        )

        user_message = (
            "Draft answers to the following application questions.\n\n"
            + "\n\n".join(sections)
        )

        response = self._call(user_message)
        result = self.extract_tool_input(response, "submit_answers")
        state["app_question_answers"] = result.get("answers", [])
        state["app_clarifying_questions"] = result.get("clarifying_questions", [])
        return state
