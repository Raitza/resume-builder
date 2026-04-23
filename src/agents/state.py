"""Shared state contract for the multi-agent pipeline.

Every agent reads from and writes to a PipelineState dict.
Each agent owns specific keys — see the plan for the ownership table.
"""

from __future__ import annotations

from typing import Optional, TypedDict


# ---------------------------------------------------------------------------
# Sub-types
# ---------------------------------------------------------------------------

class JobAnalysis(TypedDict, total=False):
    company: str
    role: str
    sector: str  # "consulting" | "clean_energy" | "ngo_philanthropy"
    requirements: list[str]
    preferred_skills: list[str]
    keywords: list[str]  # ATS keywords to mirror
    seniority_level: str  # "mid" | "senior" | "director" etc.
    culture_signals: list[str]
    core_tension: str  # the one problem this hire solves


class NarrativeStrategy(TypedDict, total=False):
    brand_angle: str
    story_arc: str
    experiences_to_highlight: list[dict]  # [{role, framing_note}, ...]
    experiences_to_omit_or_minimize: list[dict]  # [{role, reason}, ...]
    transition_framings: list[dict]  # [{from_to, framing}, ...]
    tone_and_register: str
    opening_hook: str
    differentiators: list[str]
    section_order: list[str]  # e.g. ["summary", "experience", "education", "skills"]
    authentic_questions: list[str]  # personal questions to surface (authentic mode only)


class LayoutSpec(TypedDict, total=False):
    font_family: str
    body_pt: float
    header_name_pt: float
    section_heading_pt: float
    top_margin: float  # inches
    bottom_margin: float
    left_margin: float
    right_margin: float
    line_spacing_pt: float
    space_after_pt: float
    bullet_indent: float  # inches
    heading_space_before_pt: float
    page_count_target: int  # 1 or 2
    header_style: str  # "minimal" | "centered" | "left-aligned"
    design_rationale: str
    # ATS-safe visual design
    accent_color: str  # hex color for headings/dividers, e.g. "#2B579A"
    heading_underline: bool  # colored underline below section headings
    name_color: str  # hex color for candidate name in header
    divider_style: str  # "solid_line" | "double_line" | "none"
    contact_style: str  # "pipe_separated" | "bullet_separated" | "stacked"


class DraftDocument(TypedDict, total=False):
    text: str
    assumptions_made: list[str]


class CritiqueResult(TypedDict, total=False):
    resume_gaps: list[str]
    cover_letter_gaps: list[str]
    questions: list[str]
    alignment_score: int  # 1-10
    gap_assessment: str  # summary of remaining gaps and their impact
    accepts_as_final: bool  # true when no more questions worth asking


class MemoryUpdate(TypedDict, total=False):
    updates: dict  # matches memory.json schema
    questions_asked: list[str]


class AppQuestionAnswer(TypedDict, total=False):
    question: str
    answer: str
    word_count: int
    assumptions_made: list[str]


# ---------------------------------------------------------------------------
# Top-level pipeline state
# ---------------------------------------------------------------------------

class PipelineState(TypedDict, total=False):
    # Inputs (set before pipeline starts)
    job_description: str
    resume_content: str
    memory_json: dict
    memory_md: str
    special_instructions: str   # raw text from posting (e.g. "authentic voice, no AI")
    authentic_mode: bool         # True when posting requests authentic/human-voice writing
    personal_voice_memory: dict  # memory["personal_voice"] — values, stories, motivations

    # Phase 1 — Analyst
    analysis: JobAnalysis

    # Phase 2 — Strategist
    strategy: NarrativeStrategy

    # Phase 3 — Writers + Layout Designer + App Questions
    draft_resume: DraftDocument
    draft_cover_letter: DraftDocument
    layout: LayoutSpec
    application_questions: str  # raw pasted questions from user
    app_question_answers: list[AppQuestionAnswer]
    app_clarifying_questions: list[str]

    # Phase 4 — Critic
    critique: CritiqueResult

    # User interaction (iterative)
    user_answers: str  # current round of answers
    all_answers: str  # accumulated answers across all iterations
    iteration_count: int
    iteration_capped: bool  # True when MAX_ITERATIONS reached
    diminishing_returns: bool  # True when score stopped improving
    user_feedback: str  # free-form feedback on final output

    # Phase 5 — Writers (refinement)
    final_resume: DraftDocument
    final_cover_letter: DraftDocument

    # Phase 6 — Memory
    memory_update: MemoryUpdate
