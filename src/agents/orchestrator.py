"""Pipeline orchestrator — runs all agents in the correct sequence.

Phases:
    1.  Analyst           (sequential)
    2.  Strategist        (sequential)
    3a. Layout Designer   (sequential — runs first so writers see design specs)
    3b. Resume Writer + Cover Letter  (parallel, layout-aware)
        + App Questions Agent (if application_questions provided)
    4.  Critic            (sequential)
        --- user answers questions ---
        ┌─ "Iterate" → re-runs Writers → Critic reviews again
        │   (repeat until accepts_as_final or user accepts)
        └─ "Accept & Finalize" → Phase 5
    5.  Resume Writer (final) + Cover Letter (final)   (parallel)
    6.  Memory Agent      (sequential)
"""

from __future__ import annotations

import copy
import logging
import time
from concurrent.futures import ThreadPoolExecutor, Future

from src.agents.analyst import AnalystAgent
from src.agents.strategist import StrategistAgent
from src.agents.resume_writer import ResumeWriterAgent
from src.agents.cover_letter import CoverLetterAgent
from src.agents.layout_designer import LayoutDesignerAgent
from src.agents.critic import CriticAgent
from src.agents.memory_agent import MemoryAgent
from src.agents.app_questions import AppQuestionsAgent
from src.agents.base import AgentError

logger = logging.getLogger(__name__)

# Safety cap — prevents infinite iteration loops
MAX_ITERATIONS = 5


class Pipeline:
    """Multi-agent resume builder pipeline.

    Usage from Streamlit / CLI:
        pipeline = Pipeline()
        state = pipeline.init_state(job_description, resume_content, memory_json, memory_md)
        state = pipeline.run_phase1(state)   # Analyst
        state = pipeline.run_phase2(state)   # Strategist
        state = pipeline.run_phase3_layout(state)   # Layout Designer first
        state = pipeline.run_phase3_writers(state)   # Writers (parallel, layout-aware)
        state = pipeline.run_phase4(state)   # Critic
        # ... user answers questions ...
        state["user_answers"] = combined_answers
        state = pipeline.run_phase5(state)   # Final writers (parallel)
        state = pipeline.run_phase6(state)   # Memory
    """

    def __init__(self):
        self.analyst = AnalystAgent()
        self.strategist = StrategistAgent()
        self.resume_writer = ResumeWriterAgent()
        self.cover_letter_writer = CoverLetterAgent()
        self.layout_designer = LayoutDesignerAgent()
        self.critic = CriticAgent()
        self.memory_agent = MemoryAgent()
        self.app_questions = AppQuestionsAgent()

    @staticmethod
    def init_state(
        job_description: str,
        resume_content: str,
        memory_json: dict,
        memory_md: str,
        special_instructions: str = "",
        authentic_mode: bool = False,
        include_cover_letter: bool = True,
    ) -> dict:
        """Create an initial PipelineState dict with inputs populated."""
        return {
            "job_description": job_description,
            "resume_content": resume_content,
            "memory_json": memory_json,
            "memory_md": memory_md,
            "special_instructions": special_instructions,
            "authentic_mode": authentic_mode,
            "include_cover_letter": include_cover_letter,
            "personal_voice_memory": memory_json.get("personal_voice", {}),
        }

    # ------------------------------------------------------------------
    # Phase runners
    # ------------------------------------------------------------------

    def run_phase1(self, state: dict) -> dict:
        """Phase 1: Analyst — extract structured JD analysis."""
        return self.analyst.run(state)

    def run_phase2(self, state: dict) -> dict:
        """Phase 2: Strategist — craft narrative blueprint."""
        return self.strategist.run(state)

    def run_phase3_layout(self, state: dict) -> dict:
        """Phase 3a: Layout Designer — must run BEFORE writers so they
        know the design constraints (page count, section order, spacing)."""
        try:
            result = self.layout_designer.run(copy.deepcopy(state))
            state["layout"] = result["layout"]
        except Exception as exc:
            logger.warning(
                "Layout Designer failed, using sector fallback: %s", exc
            )
            # Leave state["layout"] unset — docx_writer will use sector default
        return state

    def run_phase3_writers(self, state: dict) -> dict:
        """Phase 3b: Resume Writer + Cover Letter (+ App Questions) in parallel.

        Runs AFTER Layout Designer so the writers can see the layout specs
        (page count target, section order, font/spacing budget).
        """
        has_app_questions = bool(state.get("application_questions"))
        include_cover_letter = state.get("include_cover_letter", True)
        max_workers = (1 + int(include_cover_letter) + int(has_app_questions))

        def _delayed_run(agent, st_copy, delay_s=0):
            """Run an agent after an optional delay to stagger API calls."""
            if delay_s:
                time.sleep(delay_s)
            return agent.run(st_copy)

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            # Each thread gets its own copy of state (which now includes layout)
            f_resume: Future = pool.submit(
                _delayed_run, self.resume_writer, copy.deepcopy(state), 0
            )
            f_cover: Future | None = None
            if include_cover_letter:
                f_cover = pool.submit(
                    _delayed_run, self.cover_letter_writer, copy.deepcopy(state), 5
                )
            f_app_q: Future | None = None
            if has_app_questions:
                delay = 10 if include_cover_letter else 5
                f_app_q = pool.submit(
                    _delayed_run, self.app_questions, copy.deepcopy(state), delay
                )

            # Collect resume (always required)
            resume_state = f_resume.result()
            state["draft_resume"] = resume_state["draft_resume"]

            # Cover letter — only if requested
            if f_cover is not None:
                cover_state = f_cover.result()
                state["draft_cover_letter"] = cover_state["draft_cover_letter"]

            # App Questions — optional, fall back gracefully
            if f_app_q is not None:
                try:
                    aq_state = f_app_q.result()
                    state["app_question_answers"] = aq_state.get(
                        "app_question_answers", []
                    )
                    state["app_clarifying_questions"] = aq_state.get(
                        "app_clarifying_questions", []
                    )
                except Exception as exc:
                    logger.warning(
                        "App Questions agent failed: %s", exc
                    )
                    state["app_question_answers"] = []
                    state["app_clarifying_questions"] = []

        return state

    def run_phase4(self, state: dict) -> dict:
        """Phase 4: Critic — review drafts, identify gaps, generate questions."""
        try:
            return self.critic.run(state)
        except Exception as exc:
            logger.warning("Critic failed, proceeding without review: %s", exc)
            state["critique"] = {
                "resume_gaps": [],
                "cover_letter_gaps": [],
                "questions": [],
                "alignment_score": 0,
                "gap_assessment": "Critic unavailable — no gaps assessed.",
                "accepts_as_final": True,
            }
            return state

    def run_phase5(self, state: dict) -> dict:
        """Phase 5: Resume Writer + Cover Letter (final, parallel)."""
        include_cover_letter = state.get("include_cover_letter", True)

        def _delayed_refine(agent, st_copy, delay_s=0):
            if delay_s:
                time.sleep(delay_s)
            return agent.run_refinement(st_copy)

        max_workers = 2 if include_cover_letter else 1
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            f_resume: Future = pool.submit(
                _delayed_refine, self.resume_writer, copy.deepcopy(state), 0
            )
            f_cover: Future | None = None
            if include_cover_letter:
                f_cover = pool.submit(
                    _delayed_refine, self.cover_letter_writer, copy.deepcopy(state), 5
                )

            resume_state = f_resume.result()
            state["final_resume"] = resume_state["final_resume"]

            if f_cover is not None:
                cover_state = f_cover.result()
                state["final_cover_letter"] = cover_state["final_cover_letter"]

        return state

    def run_phase6(self, state: dict) -> dict:
        """Phase 6: Memory Agent — persist new facts."""
        try:
            return self.memory_agent.run(state)
        except Exception as exc:
            logger.warning("Memory agent failed: %s", exc)
            state["memory_update"] = {"updates": {}, "questions_asked": []}
            return state

    # ------------------------------------------------------------------
    # Iteration helpers
    # ------------------------------------------------------------------

    def run_iteration(self, state: dict) -> dict:
        """Re-run Writers on accumulated answers, then Critic reviews again.

        Used by the "Iterate" button in the UI.  Each call:
        1. Checks whether we've hit MAX_ITERATIONS — if so, force-accepts.
        2. Re-runs Resume Writer + Cover Letter Writer in parallel
           (using ``run_refinement`` so they see the accumulated answers
           and the Critic's gaps).
        3. Re-runs the Critic on the updated drafts.
        4. Detects diminishing returns (score didn't improve) and flags it.
        5. Increments ``iteration_count``.
        """
        prev_score = state.get("critique", {}).get("alignment_score", 0)
        state["iteration_count"] = state.get("iteration_count", 0) + 1
        iteration = state["iteration_count"]

        # Hard cap — no more than MAX_ITERATIONS rounds
        if iteration >= MAX_ITERATIONS:
            state["iteration_capped"] = True
            state["critique"]["accepts_as_final"] = True
            state["critique"]["gap_assessment"] = (
                f"Maximum iteration limit ({MAX_ITERATIONS}) reached. "
                "The drafts are being finalized with the information gathered so far."
            )
            return state

        # Re-run writers in parallel (refinement mode), staggered
        include_cover_letter = state.get("include_cover_letter", True)

        def _delayed_refine(agent, st_copy, delay_s=0):
            if delay_s:
                time.sleep(delay_s)
            return agent.run_refinement(st_copy)

        max_workers = 2 if include_cover_letter else 1
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            f_resume: Future = pool.submit(
                _delayed_refine, self.resume_writer, copy.deepcopy(state), 0
            )
            f_cover: Future | None = None
            if include_cover_letter:
                f_cover = pool.submit(
                    _delayed_refine, self.cover_letter_writer, copy.deepcopy(state), 5
                )

            resume_state = f_resume.result()
            # After refinement, writers put output in final_* keys — we
            # copy them back to draft_* so the Critic sees the latest version.
            state["draft_resume"] = resume_state.get(
                "final_resume", state.get("draft_resume")
            )

            if f_cover is not None:
                cover_state = f_cover.result()
                state["draft_cover_letter"] = cover_state.get(
                    "final_cover_letter", state.get("draft_cover_letter")
                )

        # Clear final keys — they'll be set again in Phase 5 (Accept & Finalize)
        state.pop("final_resume", None)
        state.pop("final_cover_letter", None)

        # Re-run Critic on the updated drafts
        state = self.run_phase4(state)

        # Diminishing returns detection — if score didn't improve, flag it
        new_score = state.get("critique", {}).get("alignment_score", 0)
        if new_score <= prev_score and iteration >= 2:
            state["diminishing_returns"] = True
        else:
            state["diminishing_returns"] = False

        return state

    def run_app_questions(self, state: dict) -> dict:
        """Run the App Questions agent standalone.

        Called from the UI when the user pastes application questions
        after Phase 2 has already completed.
        """
        try:
            result_state = self.app_questions.run(copy.deepcopy(state))
            state["app_question_answers"] = result_state.get(
                "app_question_answers", []
            )
            state["app_clarifying_questions"] = result_state.get(
                "app_clarifying_questions", []
            )
        except Exception as exc:
            logger.warning("App Questions agent failed: %s", exc)
            state["app_question_answers"] = []
            state["app_clarifying_questions"] = []
        return state
