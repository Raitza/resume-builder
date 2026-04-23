"""Analyst Agent — extracts structured intelligence from a job description."""

from __future__ import annotations

from src.agents.base import BaseAgent, AgentError
from config import MODEL_SONNET

_TOOL = {
    "name": "submit_analysis",
    "description": "Submit the structured job analysis extracted from the job description.",
    "input_schema": {
        "type": "object",
        "properties": {
            "company": {"type": "string", "description": "Hiring company name"},
            "role": {"type": "string", "description": "Exact job title"},
            "sector": {
                "type": "string",
                "enum": ["consulting", "clean_energy", "ngo_philanthropy"],
                "description": "Industry sector classification",
            },
            "requirements": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Hard, non-negotiable skills and qualifications",
            },
            "preferred_skills": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Nice-to-have skills that strengthen a candidate",
            },
            "keywords": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Exact ATS keywords and phrases from the posting",
            },
            "seniority_level": {
                "type": "string",
                "description": "Inferred seniority: entry, mid, senior, director, executive",
            },
            "culture_signals": {
                "type": "array",
                "items": {"type": "string"},
                "description": "What the organization values beyond skills",
            },
            "core_tension": {
                "type": "string",
                "description": "The one central problem this hire is meant to solve",
            },
        },
        "required": [
            "company", "role", "sector", "requirements", "keywords",
            "seniority_level", "core_tension",
        ],
    },
}


class AnalystAgent(BaseAgent):
    name = "Analyst"
    prompt_file = "analyst.md"
    max_tokens = 1024
    model = MODEL_SONNET
    tools = [_TOOL]
    tool_choice = {"type": "tool", "name": "submit_analysis"}
    needs_candidate_profile = False

    def run(self, state: dict) -> dict:
        job_desc = state.get("job_description", "")
        if not job_desc:
            raise AgentError(self.name, ValueError("No job_description in state"))

        response = self._call(
            f"Analyze this job description:\n\n{job_desc}"
        )

        analysis = self.extract_tool_input(response, "submit_analysis")
        state["analysis"] = analysis
        return state
