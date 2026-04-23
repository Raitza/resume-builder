"""
Resume Builder — Multi-agent Streamlit interface
Run: streamlit run app.py
"""

import json
import os
import re
import sys
from datetime import datetime

import subprocess
import streamlit as st
import streamlit.components.v1 as components

# Ensure src/ is importable from project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import CANDIDATE_NAME, CANDIDATE_LINKEDIN_URL
from src.reader import read_all_resumes, read_memory_md_files
from src.docx_writer import write_docx, estimate_page_count, ats_check, verify_docx, _SECTOR_FORMATS
from src.memory_updater import update_memory
from src.job_scraper import scrape_job_description
from src.agents.orchestrator import Pipeline
from src.feedback_reader import pair_feedback_with_output, get_already_analyzed
from src.agents.feedback_analyst import FeedbackAnalyst

PROFILES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profiles")
MEMORY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory", "memory.json")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
MEMORY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory")

# Number of concurrent application slots
_SLOTS = ["app1", "app2", "app3", "app4"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_memory() -> dict:
    if os.path.exists(MEMORY_PATH):
        with open(MEMORY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _session_cache_path(slot: str) -> str:
    return os.path.join(MEMORY_DIR, f"session_cache_{slot}.json")


def _save_session(slot: str, pipeline_state: dict, step: str) -> None:
    """Persist pipeline state + UI step to disk so a server restart can restore it."""
    os.makedirs(MEMORY_DIR, exist_ok=True)
    with open(_session_cache_path(slot), "w", encoding="utf-8") as f:
        json.dump({"step": step, "pipeline_state": pipeline_state}, f, ensure_ascii=False, indent=2)


def _load_session(slot: str) -> dict | None:
    """Return cached session dict if it exists, else None."""
    path = _session_cache_path(slot)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def _clear_session(slot: str) -> None:
    """Delete the on-disk session cache for a slot."""
    path = _session_cache_path(slot)
    if os.path.exists(path):
        os.remove(path)


def _save_profile(company: str, role: str, job_desc: str) -> str:
    os.makedirs(PROFILES_DIR, exist_ok=True)
    slug = f"{company}_{role}".replace(" ", "_").replace("/", "-")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"profile_{slug}_{timestamp}.txt"
    filepath = os.path.join(PROFILES_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(job_desc)
    return filename


def _parse_questions(text: str) -> list[str]:
    """Split a questions block into individual question strings."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    questions: list[str] = []
    current: list[str] = []
    for line in lines:
        if re.match(r'^(\d+[.):\s]|\*\*\d|[-•]\s)', line):
            if current:
                questions.append(" ".join(current))
                current = []
            clean = re.sub(r'^(\*\*\d+[.):]?\*?\*?|\d+[.):\s]+|[-•]\s+)', "", line).strip()
            if clean:
                current = [clean]
        else:
            current.append(line)
    if current:
        questions.append(" ".join(current))
    return [q for q in questions if q] or [text.strip()]


def _slugify(text: str) -> str:
    return text.strip().replace(" ", "_").replace("/", "-")


def _clarify_question(question: str, analysis: dict) -> str:
    """Lightweight Claude call to rephrase a question in plain language."""
    role = analysis.get("role", "the role")
    company = analysis.get("company", "the company")
    prompt = (
        f"A resume reviewer asked this question about a candidate applying for "
        f"{role} at {company}:\n\n\"{question}\"\n\n"
        f"Please rephrase this in 2-3 plain-language sentences so the candidate "
        f"understands exactly what info is needed and WHY the answer would "
        f"improve their application. Be concise and direct."
    )
    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "text"],
            capture_output=True, text=True, timeout=20, shell=True,
        )
    except subprocess.TimeoutExpired:
        return "⏱️ Clarification timed out (20s). Try answering based on the question text directly."
    if result.returncode != 0:
        return f"Could not clarify: {result.stderr.strip() or 'Unknown error'}"
    return result.stdout.strip()


def _output_folder_for(company: str, role: str) -> str:
    return os.path.join(OUTPUT_DIR, f"{_slugify(company)}_{_slugify(role)}")


# ---------------------------------------------------------------------------
# Design preview helpers
# ---------------------------------------------------------------------------

_FICTIONAL_RESUME = """\
Brenda Rain

New York, NY  |  brenda.rain@email.com  |  +1 (646) 555-0198

PROFESSIONAL SUMMARY
Accomplished development and partnerships professional with 9 years of experience mobilizing capital and building institutional relationships across the NGO, philanthropy, and impact investing sectors. Track record of securing multi-year funding from foundations, bilateral donors, and DFIs to deliver programs at scale.

EXPERIENCE

Senior Development Manager
Open Society Foundations — New York, NY  |  Jan 2021 – Present
• Steered a $15M institutional fundraising campaign, surpassing targets by 22% over two consecutive years
• Cultivated relationships with 50+ funders including Gates Foundation, Ford Foundation, and USAID
• Designed and rolled out a MEL framework adopted across four regional offices, reducing reporting cycles by 35%
• Led a cross-functional team of 6 to develop the organization's first multi-year resource mobilization strategy

Development Associate
International Rescue Committee — Washington, DC  |  Jun 2017 – Dec 2020
• Managed a donor portfolio of 30 mid-level institutions, generating $3.1M in annual revenue
• Co-authored grant proposals to USAID, European Commission, and UNHCR totalling $6.2M (82% success rate)
• Coordinated three annual gala fundraising events, each raising $600K+

Program Officer, Climate & Energy Transition
ClimateWorks Foundation — San Francisco, CA  |  Aug 2015 – May 2017
• Grant-managed a $4M portfolio of clean-energy advocacy grants across Latin America
• Produced bi-annual landscape analyses informing foundation strategy on carbon markets

EDUCATION

Master of Public Administration (MPA), International Development
Columbia University, School of International and Public Affairs  |  2015

Bachelor of Arts, Political Science & Environmental Studies
University of Michigan  |  2013  |  Magna Cum Laude

SKILLS
Institutional Fundraising  |  Grant Writing & Management  |  MEL Frameworks  |  Salesforce CRM  |  Budget Oversight  |  Stakeholder Engagement  |  Program Design  |  Spanish (Professional)\
"""


def _resume_to_html(content: str, fmt: dict) -> str:
    bp = fmt["body_pt"]
    np_ = fmt["header_name_pt"]
    hp = fmt["section_heading_pt"]
    ls = fmt["line_spacing_pt"]
    sa = fmt["space_after_pt"]
    hsbp = fmt["heading_space_before_pt"]
    bi = fmt["bullet_indent"]
    ff = fmt.get("font_family", "Calibri")
    accent = fmt.get("accent_color", "#333333")
    name_color = fmt.get("name_color") or accent
    use_underline = fmt.get("heading_underline", False)
    divider = fmt.get("divider_style", "none")

    rows: list[str] = []
    first = True
    for line in content.strip().splitlines():
        s = line.rstrip()
        if not s:
            rows.append(f'<div style="height:{sa}pt"></div>')
            continue
        if first and s.strip().lower() == CANDIDATE_NAME.lower():
            rows.append(
                f'<p style="text-align:center;font-weight:bold;font-size:{np_}pt;'
                f'color:{name_color};margin:0 0 4pt 0;line-height:{ls}pt;">{s}</p>'
            )
            first = False
            continue
        first = False
        if (s.isupper() and len(s) <= 60) or (s.endswith(":") and len(s) <= 60 and s[0].isupper()):
            border_css = f"border-bottom:1px solid {accent};" if use_underline else ""
            divider_css = ""
            if divider == "solid_line":
                divider_css = f'<hr style="border:none;border-top:1px solid {accent};margin:0 0 2pt 0;">'
            elif divider == "double_line":
                divider_css = f'<hr style="border:none;border-top:3px double {accent};margin:0 0 2pt 0;">'
            rows.append(
                f'{divider_css}'
                f'<p style="font-weight:bold;font-size:{hp}pt;color:{accent};'
                f'margin:{hsbp}pt 0 2pt 0;{border_css}line-height:{ls}pt;">{s}</p>'
            )
        elif s.startswith("• ") or s.startswith("- "):
            rows.append(
                f'<p style="margin:0 0 {sa}pt {bi*72}pt;font-size:{bp}pt;line-height:{ls}pt;">'
                f'&#8226;&nbsp;{s[2:]}</p>'
            )
        else:
            rows.append(
                f'<p style="margin:0 0 {sa}pt 0;font-size:{bp}pt;line-height:{ls}pt;">{s}</p>'
            )

    body = "\n".join(rows)
    return f"""
<div style="background:#e8e8e8;padding:24px;min-height:800px;font-family:{ff},'Segoe UI',sans-serif;">
  <div style="background:white;width:8.5in;max-width:100%;margin:0 auto;
              padding:{fmt['top_margin']}in {fmt['right_margin']}in {fmt['bottom_margin']}in {fmt['left_margin']}in;
              box-shadow:0 3px 14px rgba(0,0,0,0.18);box-sizing:border-box;">
    <div style="display:flex;justify-content:space-between;align-items:baseline;
                border-bottom:2px solid {accent};padding-bottom:5pt;margin-bottom:8pt;">
      <span style="font-weight:bold;font-size:{np_}pt;color:{name_color};">{CANDIDATE_NAME}</span>
      <a href="{CANDIDATE_LINKEDIN_URL}" style="font-size:{bp}pt;color:#0563C1;text-decoration:underline;">{CANDIDATE_LINKEDIN_URL}</a>
    </div>
    {body}
  </div>
</div>
"""


# ---------------------------------------------------------------------------
# Per-slot defaults
# ---------------------------------------------------------------------------

_BASE_DEFAULTS = {
    "step": "input",
    "job_desc": "",
    "scraped_preview": "",
    "scrape_error": "",
    "pipeline_state": {},
    "clarified_questions": {},
    "has_app_questions": False,
    "app_questions_text": "",
    "special_instructions": "",
    "authentic_mode": False,
    "include_cover_letter": True,
    "late_app_questions": "",
}


def _slot_key(slot: str, key: str) -> str:
    return f"{slot}_{key}"


def _ss(slot: str, key: str):
    """Read a slot-namespaced session state value."""
    return st.session_state[_slot_key(slot, key)]


def _set_ss(slot: str, key: str, value) -> None:
    """Write a slot-namespaced session state value."""
    st.session_state[_slot_key(slot, key)] = value


def _init_slot_defaults(slot: str) -> None:
    for key, default in _BASE_DEFAULTS.items():
        sk = _slot_key(slot, key)
        if sk not in st.session_state:
            st.session_state[sk] = default


def _slot_label(slot: str) -> str:
    """Return a human-readable tab label, enriched with company/role if available."""
    labels = {"app1": "App 1", "app2": "App 2", "app3": "App 3", "app4": "App 4"}
    base = labels.get(slot, slot)
    ps = st.session_state.get(_slot_key(slot, "pipeline_state"), {})
    analysis = ps.get("analysis", {}) if ps else {}
    company = analysis.get("company", "")
    role = analysis.get("role", "")
    if company and role:
        short_company = company[:14] + "…" if len(company) > 14 else company
        short_role = role[:14] + "…" if len(role) > 14 else role
        return f"{base} · {short_company}"
    return base


# ---------------------------------------------------------------------------
# Builder render function (one per slot)
# ---------------------------------------------------------------------------

def _render_builder(slot: str) -> None:
    ss = st.session_state  # convenience alias

    _init_slot_defaults(slot)

    # ── Auto-restore on first load after a crash ──────────────────────────
    restore_key = _slot_key(slot, "_show_restore_prompt")
    cache_key   = _slot_key(slot, "_restore_cache")

    if restore_key not in ss:
        _cached = _load_session(slot)
        if _cached and _cached.get("pipeline_state") and _cached.get("step", "input") != "input":
            ss[restore_key] = True
            ss[cache_key]   = _cached
        else:
            ss[restore_key] = False

    if ss[restore_key]:
        _cached   = ss[cache_key]
        _analysis = _cached["pipeline_state"].get("analysis", {})
        _company  = _analysis.get("company", "?")
        _role     = _analysis.get("role", "?")
        st.info(
            f"🔄 **Sesión previa encontrada** — {_company} · {_role}  \n"
            "¿Deseas retomar donde lo dejaste o empezar desde cero?"
        )
        col_r, col_n = st.columns(2)
        if col_r.button("▶ Retomar sesión", type="primary", use_container_width=True,
                         key=f"{slot}_restore_btn"):
            ss[_slot_key(slot, "pipeline_state")] = _cached["pipeline_state"]
            ss[_slot_key(slot, "step")]            = _cached["step"]
            ss[restore_key]                        = False
            st.rerun()
        if col_n.button("🗑 Nueva sesión", use_container_width=True,
                         key=f"{slot}_new_btn"):
            _clear_session(slot)
            ss[restore_key] = False
            st.rerun()
        return  # stop rendering this slot only — other tabs stay unaffected

    # Lazy pipeline singleton per slot
    pipeline_key = _slot_key(slot, "pipeline")
    if pipeline_key not in ss:
        ss[pipeline_key] = Pipeline()
    pipeline: Pipeline = ss[pipeline_key]
    ps = ss[_slot_key(slot, "pipeline_state")]  # shorthand (mutable dict)

    # Helper to reset this slot
    def _reset():
        for key, default in _BASE_DEFAULTS.items():
            ss[_slot_key(slot, key)] = default
        _clear_session(slot)

    # ── STEP 1: Input ────────────────────────────────────────────────────
    if ss[_slot_key(slot, "step")] == "input":
        st.subheader("Job description")
        jd_method = st.radio(
            "How would you like to provide the job description?",
            options=["Option A — Paste a URL (auto-scrape)", "Option B — Paste text directly"],
            index=0,
            label_visibility="collapsed",
            key=f"{slot}_jd_method",
        )

        job_desc = ""

        if "Option A" in jd_method:
            url_col, btn_col = st.columns([4, 1])
            with url_col:
                url_input = st.text_input("Job posting URL", placeholder="https://...",
                                          key=f"{slot}_url_input")
            with btn_col:
                st.write("")
                fetch_clicked = st.button("Fetch", use_container_width=True,
                                          key=f"{slot}_fetch_btn")

            if fetch_clicked and url_input:
                with st.spinner("Scraping job description..."):
                    text, err = scrape_job_description(url_input)
                if err:
                    ss[_slot_key(slot, "scrape_error")]    = err
                    ss[_slot_key(slot, "scraped_preview")] = ""
                    ss[_slot_key(slot, "job_desc")]        = ""
                else:
                    ss[_slot_key(slot, "scrape_error")]    = ""
                    ss[_slot_key(slot, "scraped_preview")] = text[:400] + ("..." if len(text) > 400 else "")
                    ss[_slot_key(slot, "job_desc")]        = text

            if ss[_slot_key(slot, "scrape_error")]:
                st.error(ss[_slot_key(slot, "scrape_error")])
                st.info("Switch to **Option B** and paste the job description text directly.")
            if ss[_slot_key(slot, "scraped_preview")]:
                st.success("Job description fetched successfully.")
                st.caption("Preview (first 400 chars):")
                st.text(ss[_slot_key(slot, "scraped_preview")])

            job_desc = ss[_slot_key(slot, "job_desc")]
        else:
            pasted = st.text_area(
                "Paste job description here",
                value=ss[_slot_key(slot, "job_desc")] if not ss[_slot_key(slot, "scraped_preview")] else "",
                height=300,
                placeholder="Paste the full job description text...",
                key=f"{slot}_jd_paste",
            )
            job_desc = pasted.strip()

        st.divider()

        # Cover letter toggle
        st.subheader("Cover Letter")
        has_cl = st.radio(
            "Does this application require a cover letter?",
            options=["Yes", "No"],
            index=0 if ss[_slot_key(slot, "include_cover_letter")] else 1,
            horizontal=True,
            key=f"{slot}_cl_toggle",
        )
        ss[_slot_key(slot, "include_cover_letter")] = (has_cl == "Yes")

        st.divider()

        # Application questions toggle
        st.subheader("Application Questions")
        has_aq = st.radio(
            "Does this application have specific questions to answer (essay prompts)?",
            options=["No", "Yes"],
            index=1 if ss[_slot_key(slot, "has_app_questions")] else 0,
            horizontal=True,
            key=f"{slot}_aq_toggle",
        )
        ss[_slot_key(slot, "has_app_questions")] = (has_aq == "Yes")

        if ss[_slot_key(slot, "has_app_questions")]:
            ss[_slot_key(slot, "app_questions_text")] = st.text_area(
                "Paste the application questions here",
                value=ss[_slot_key(slot, "app_questions_text")],
                height=200,
                placeholder=(
                    "e.g.\n"
                    "1. Why do you want to work at [Company]? (max 300 words)\n"
                    "2. Describe a time you led a team through ambiguity.\n"
                    "3. What is your approach to stakeholder engagement?"
                ),
                key=f"{slot}_aq_paste",
            )

        st.divider()

        # Special instructions / authentic voice mode
        st.subheader("Special Instructions")
        st.caption(
            "If the posting has specific writing instructions (e.g. *'authentic voice, no AI'*, "
            "*'thoughtful cover letter'*, *'in your own words'*), paste them here. "
            "This activates **Authentic Voice Mode** — the pipeline will ask deeper personal "
            "questions and write the cover letter in a genuinely human voice."
        )
        special_instructions_input = st.text_area(
            "Paste any special instructions from the posting (optional)",
            value=ss[_slot_key(slot, "special_instructions")],
            height=80,
            placeholder=(
                "e.g. \"We want to hear from you in your own authentic voice, "
                "so we request that you refrain from using AI to compose your letter...\""
            ),
            key=f"{slot}_special_instructions_input",
        )
        ss[_slot_key(slot, "special_instructions")] = special_instructions_input

        _AUTHENTIC_KEYWORDS = [
            "authentic voice", "own voice", "your own voice", "authentic",
            "no ai", "without ai", "refrain from using ai", "refrain from ai",
            "thoughtful cover", "in your own words", "human voice",
        ]
        _combined_text = (special_instructions_input + " " + job_desc).lower()
        detected_authentic = any(kw in _combined_text for kw in _AUTHENTIC_KEYWORDS)
        ss[_slot_key(slot, "authentic_mode")] = detected_authentic
        if detected_authentic:
            st.info(
                "✍️ **Authentic Voice Mode detected** — The pipeline will ask personal "
                "questions about your values, stories, and connection to the mission, "
                "and write the cover letter in a genuinely human voice."
            )

        st.divider()

        if st.button("Analyze & Generate", type="primary", use_container_width=True,
                     key=f"{slot}_analyze_btn"):
            if not job_desc:
                st.error("Please provide a job description.")
            else:
                ss[_slot_key(slot, "job_desc")] = job_desc

                try:
                    resume_content = read_all_resumes()
                except FileNotFoundError as exc:
                    st.error(f"Could not load resumes: {exc}")
                    st.stop()

                memory_md   = read_memory_md_files()
                memory_json = _load_memory()

                state = Pipeline.init_state(
                    job_description=job_desc,
                    resume_content=resume_content,
                    memory_json=memory_json,
                    memory_md=memory_md,
                    special_instructions=ss[_slot_key(slot, "special_instructions")],
                    authentic_mode=ss[_slot_key(slot, "authentic_mode")],
                    include_cover_letter=ss[_slot_key(slot, "include_cover_letter")],
                )

                if ss[_slot_key(slot, "has_app_questions")] and ss[_slot_key(slot, "app_questions_text")].strip():
                    state["application_questions"] = ss[_slot_key(slot, "app_questions_text")].strip()

                # Phase 1: Analyst
                try:
                    with st.spinner("Phase 1/4 — Analyzing job description..."):
                        state = pipeline.run_phase1(state)
                except Exception as exc:
                    st.error(f"Analyst failed: {exc}")
                    st.stop()

                analysis = state.get("analysis", {})
                company  = analysis.get("company", "Unknown")
                role     = analysis.get("role", "Unknown")

                folder = _output_folder_for(company, role)
                if os.path.exists(folder) and os.listdir(folder):
                    st.warning(
                        f"Previous output for **{company} — {role}** exists "
                        f"and will be replaced when you finalize."
                    )

                _save_profile(company, role, job_desc)

                # Phase 2: Strategist
                try:
                    with st.spinner("Phase 2/4 — Crafting narrative strategy..."):
                        state = pipeline.run_phase2(state)
                except Exception as exc:
                    st.error(f"Strategist failed: {exc}")
                    st.stop()

                # Phase 3a: Layout Designer
                try:
                    with st.spinner("Phase 3a — Designing layout (margins, fonts, colors, page target)..."):
                        state = pipeline.run_phase3_layout(state)
                except Exception as exc:
                    st.warning(f"Layout Designer failed (will use sector defaults): {exc}")

                # Phase 3b: Writers
                try:
                    spinner_label = "Phase 3b — Writing resume & cover letter (layout-aware)..."
                    if state.get("application_questions"):
                        spinner_label = "Phase 3b — Writing resume, cover letter & answering app questions (layout-aware)..."
                    with st.spinner(spinner_label):
                        state = pipeline.run_phase3_writers(state)
                except Exception as exc:
                    st.error(f"Writing phase failed: {exc}")
                    st.stop()

                # Phase 4: Critic
                with st.spinner("Phase 4/4 — Reviewing drafts..."):
                    state = pipeline.run_phase4(state)

                state["iteration_count"] = 0
                ss[_slot_key(slot, "pipeline_state")]     = state
                ss[_slot_key(slot, "clarified_questions")] = {}
                ss[_slot_key(slot, "step")]               = "drafts_review"
                _save_session(slot, state, "drafts_review")
                st.rerun()

    # ── STEP 2: Drafts Review + Iteration Loop ────────────────────────────
    elif ss[_slot_key(slot, "step")] == "drafts_review":
        analysis  = ps.get("analysis", {})
        strategy  = ps.get("strategy", {})
        critique  = ps.get("critique", {})
        layout    = ps.get("layout", {})

        company   = analysis.get("company", "Unknown")
        role      = analysis.get("role", "Unknown")
        sector    = analysis.get("sector", "ngo_philanthropy")
        iteration = ps.get("iteration_count", 0)

        score       = critique.get("alignment_score", 0)
        score_color = "green" if score >= 7 else ("orange" if score >= 4 else "red")
        iter_label  = f" &nbsp;|&nbsp; Iteration: **{iteration}**" if iteration > 0 else ""
        st.info(
            f"**{company}** — {role} &nbsp;|&nbsp; "
            f"Sector: `{sector}` &nbsp;|&nbsp; "
            f"Alignment: :{score_color}[**{score}/10**]"
            f"{iter_label}"
        )

        iteration_capped   = ps.get("iteration_capped", False)
        diminishing_returns = ps.get("diminishing_returns", False)
        MAX_ITERATIONS     = 5

        accepts_final  = critique.get("accepts_as_final", False)
        gap_assessment = critique.get("gap_assessment", "")

        if iteration_capped:
            st.error(
                f"**Iteration limit reached ({MAX_ITERATIONS}).** "
                "The pipeline is moving to finalization with the best version so far."
            )
        elif accepts_final:
            st.success("The Critic recommends **finalizing** — no more valuable questions to ask.")
        elif diminishing_returns:
            st.warning(
                "⚠️ **Diminishing returns detected** — the alignment score hasn't improved. "
                "Consider **accepting & finalizing** rather than iterating further."
            )
        else:
            remaining = MAX_ITERATIONS - iteration
            st.warning(
                f"The Critic recommends **answering more questions** to improve the output. "
                f"({remaining} iteration{'s' if remaining != 1 else ''} remaining)"
            )
        if gap_assessment:
            with st.expander("Gap Assessment"):
                st.markdown(gap_assessment)

        with st.expander("Narrative Strategy", expanded=False):
            st.markdown(f"**Brand angle:** {strategy.get('brand_angle', 'N/A')}")
            st.markdown(f"**Story arc:** {strategy.get('story_arc', 'N/A')}")
            st.markdown(f"**Tone:** {strategy.get('tone_and_register', 'N/A')}")
            st.markdown(f"**Cover letter hook:** {strategy.get('opening_hook', 'N/A')}")
            diffs = strategy.get("differentiators", [])
            if diffs:
                st.markdown("**Differentiators:**")
                for d in diffs:
                    st.markdown(f"- {d}")
            highlights = strategy.get("experiences_to_highlight", [])
            if highlights:
                st.markdown("**Experiences to highlight:**")
                for h in highlights:
                    st.markdown(f"- **{h.get('role', '')}** — {h.get('framing_note', '')}")

        if layout:
            with st.expander("Layout Design"):
                st.markdown(
                    f"**Font:** {layout.get('font_family', 'Calibri')} &nbsp;|&nbsp; "
                    f"**Body:** {layout.get('body_pt', '')}pt &nbsp;|&nbsp; "
                    f"**Pages:** {layout.get('page_count_target', '')} &nbsp;|&nbsp; "
                    f"**Margins:** {layout.get('left_margin', '')}\" L/R, {layout.get('top_margin', '')}\" T/B"
                )
                if layout.get("accent_color"):
                    c = layout["accent_color"]
                    st.markdown(
                        f"**Accent:** <span style='color:{c};font-weight:bold;'>{c}</span> &nbsp;|&nbsp; "
                        f"**Underlines:** {'Yes' if layout.get('heading_underline') else 'No'} &nbsp;|&nbsp; "
                        f"**Dividers:** {layout.get('divider_style', 'none')}",
                        unsafe_allow_html=True,
                    )
                if layout.get("design_rationale"):
                    st.caption(layout["design_rationale"])

        st.subheader("Draft Resume")
        draft_resume = ps.get("draft_resume", {})
        st.text_area(
            "resume_preview",
            value=draft_resume.get("text", "(no resume generated)"),
            height=420,
            disabled=True,
            label_visibility="collapsed",
            key=f"{slot}_resume_preview",
        )
        if draft_resume.get("assumptions_made"):
            with st.expander("Resume assumptions"):
                for a in draft_resume["assumptions_made"]:
                    st.markdown(f"- {a}")

        if ps.get("include_cover_letter", True):
            st.subheader("Draft Cover Letter")
            draft_cover = ps.get("draft_cover_letter", {})
            st.text_area(
                "cover_letter_preview",
                value=draft_cover.get("text", "(no cover letter generated)"),
                height=300,
                disabled=True,
                label_visibility="collapsed",
                key=f"{slot}_cover_preview",
            )

        app_answers = ps.get("app_question_answers", [])
        if app_answers:
            st.subheader("Application Question Answers")
            for i, aq in enumerate(app_answers):
                st.markdown(f"**Q{i+1}:** {aq.get('question', '')}")
                if aq.get("word_count"):
                    st.caption(f"Word count: {aq['word_count']}")
                st.text_area(
                    f"app_answer_{i}",
                    value=aq.get("answer", ""),
                    height=150,
                    key=f"{slot}_app_answer_{i}",
                    label_visibility="collapsed",
                )
                if aq.get("assumptions_made"):
                    st.caption(f"Assumptions: {', '.join(aq['assumptions_made'])}")

        app_clarifying = ps.get("app_clarifying_questions", [])
        if app_clarifying:
            st.markdown("**The App Questions agent needs more info:**")
            for i, cq in enumerate(app_clarifying):
                st.markdown(f"- {cq}")

        questions = critique.get("questions", [])
        if questions:
            st.subheader("Reviewer Questions")
            for i, q in enumerate(questions):
                st.markdown(f"**{i + 1}.** {q}")

                clarify_key = f"{slot}_clarify_{iteration}_{i}"
                if st.button("Clarify ▾", key=clarify_key):
                    with st.spinner("Getting clarification..."):
                        clarification = _clarify_question(q, analysis)
                    ss[_slot_key(slot, "clarified_questions")][f"{iteration}_{i}"] = clarification

                clar_key = f"{iteration}_{i}"
                if clar_key in ss[_slot_key(slot, "clarified_questions")]:
                    st.info(ss[_slot_key(slot, "clarified_questions")][clar_key])

                st.text_area(
                    f"Answer {i + 1}",
                    placeholder="Your answer... (leave blank to skip)",
                    height=80,
                    label_visibility="collapsed",
                    key=f"{slot}_q_answer_{i}",
                )

        resume_gaps = critique.get("resume_gaps", [])
        cover_gaps  = critique.get("cover_letter_gaps", [])
        if resume_gaps or cover_gaps:
            with st.expander("Identified Gaps"):
                if resume_gaps:
                    st.markdown("**Resume gaps:**")
                    for g in resume_gaps:
                        st.markdown(f"- {g}")
                if cover_gaps:
                    st.markdown("**Cover letter gaps:**")
                    for g in cover_gaps:
                        st.markdown(f"- {g}")

        # ── Option A: Late application questions ──────────────────────────
        with st.expander("📋 Application questions appeared? Add them here", expanded=False):
            st.caption(
                "Paste any essay questions or prompts from the application form. "
                "The agent will use everything worked through in this iteration — "
                "your answers, the drafts, and the full strategy."
            )
            late_aq_text = st.text_area(
                "Application questions",
                value=ss.get(_slot_key(slot, "late_app_questions"), ""),
                height=150,
                placeholder="e.g.\n1. Why do you want to work here? (300 words)\n2. Describe a time you led through ambiguity.",
                key=f"{slot}_late_aq_input",
                label_visibility="collapsed",
            )
            ss[_slot_key(slot, "late_app_questions")] = late_aq_text

            if st.button("Generate Answers", key=f"{slot}_late_aq_btn", use_container_width=True):
                if not late_aq_text.strip():
                    st.error("Please paste at least one question.")
                else:
                    ps["application_questions"] = late_aq_text.strip()
                    try:
                        with st.spinner("Drafting answers using full iteration context..."):
                            new_state = pipeline.run_app_questions(ps)
                            ss[_slot_key(slot, "pipeline_state")] = new_state
                            ps = new_state
                    except Exception as exc:
                        st.error(f"App Questions failed: {exc}")
                    _save_session(slot, ps, "drafts_review")
                    st.rerun()

        st.divider()
        col_back, col_iterate, col_finalize = st.columns([1, 2, 2])
        with col_back:
            if st.button("Start over", key=f"{slot}_start_over"):
                _reset()
                st.rerun()

        with col_iterate:
            iterate_disabled = iteration_capped or (iteration >= MAX_ITERATIONS)
            if st.button(
                "Iterate" if not iterate_disabled else "Iterate (limit reached)",
                use_container_width=True,
                disabled=iterate_disabled,
                key=f"{slot}_iterate_btn",
            ):
                new_answers = "\n\n".join(
                    f"Q{i+1}: {q}\nA: {ss.get(f'{slot}_q_answer_{i}', '').strip() or '(no answer provided)'}"
                    for i, q in enumerate(questions)
                ) if questions else ""

                prev_answers = ps.get("all_answers", "")
                if prev_answers and new_answers:
                    ps["all_answers"] = prev_answers + "\n\n---\n\n" + new_answers
                elif new_answers:
                    ps["all_answers"] = new_answers
                ps["user_answers"] = new_answers

                try:
                    with st.spinner(
                        f"Iteration {iteration + 1} — Rewriting resume & cover letter "
                        f"with your answers, then re-evaluating with the Critic..."
                    ):
                        new_state = pipeline.run_iteration(ps)
                        ss[_slot_key(slot, "pipeline_state")] = new_state
                except Exception as exc:
                    st.error(f"Iteration failed: {exc}")
                    st.stop()

                ss[_slot_key(slot, "clarified_questions")] = {}
                _save_session(slot, ss[_slot_key(slot, "pipeline_state")], "drafts_review")
                st.rerun()

        with col_finalize:
            if st.button("Accept & Finalize", type="primary", use_container_width=True,
                          key=f"{slot}_finalize_btn"):
                new_answers = "\n\n".join(
                    f"Q{i+1}: {q}\nA: {ss.get(f'{slot}_q_answer_{i}', '').strip() or '(no answer provided)'}"
                    for i, q in enumerate(questions)
                ) if questions else ""

                prev_answers = ps.get("all_answers", "")
                if prev_answers and new_answers:
                    ps["all_answers"] = prev_answers + "\n\n---\n\n" + new_answers
                elif new_answers:
                    ps["all_answers"] = new_answers
                ps["user_answers"] = new_answers

                try:
                    _spinner_msg = "Generating final resume & cover letter..." if ps.get("include_cover_letter", True) else "Generating final resume..."
                    with st.spinner(_spinner_msg):
                        new_state = pipeline.run_phase5(ps)
                        ss[_slot_key(slot, "pipeline_state")] = new_state
                        ps = new_state
                except Exception as exc:
                    st.error(f"Final writing failed: {exc}")
                    st.stop()

                output_paths = {}
                final_resume = ps.get("final_resume", {})
                final_cover  = ps.get("final_cover_letter", {})

                if final_resume.get("text"):
                    result = write_docx(
                        final_resume["text"], company, role, "resume",
                        sector=sector, layout=layout or None,
                    )
                    output_paths["resume"] = result["path"]
                    if result.get("page_target") and result["estimated_pages"] > result["page_target"]:
                        st.warning(
                            f"The resume is estimated at **{result['estimated_pages']} pages**, "
                            f"exceeding the target of **{result['page_target']}**. "
                            f"Consider providing feedback to shorten it."
                        )
                    ps["ats_results"]      = ats_check(result["path"])
                    ps["formatting_report"] = verify_docx(result["path"])

                if final_cover.get("text"):
                    result = write_docx(
                        final_cover["text"], company, role, "cover_letter",
                        sector=sector, layout=layout or None,
                    )
                    output_paths["cover_letter"] = result["path"]
                    if result.get("page_target") and result["estimated_pages"] > result["page_target"]:
                        st.warning(
                            f"The cover letter is estimated at **{result['estimated_pages']} pages**, "
                            f"exceeding the target of **{result['page_target']}**."
                        )

                if app_answers:
                    folder = _output_folder_for(company, role)
                    os.makedirs(folder, exist_ok=True)
                    answers_path = os.path.join(folder, "application_answers.txt")
                    with open(answers_path, "w", encoding="utf-8") as f:
                        for i, aq in enumerate(app_answers):
                            edited = ss.get(f"{slot}_app_answer_{i}", aq.get("answer", ""))
                            f.write(f"Q{i+1}: {aq.get('question', '')}\n\n")
                            f.write(f"{edited}\n\n")
                            f.write("---\n\n")
                    output_paths["application_answers"] = answers_path

                all_qa = ps.get("all_answers", "")
                if all_qa:
                    folder = _output_folder_for(company, role)
                    os.makedirs(folder, exist_ok=True)
                    qa_path = os.path.join(folder, "qa_answers.txt")
                    with open(qa_path, "w", encoding="utf-8") as f:
                        f.write(f"Q&A from iteration review — {company} / {role}\n")
                        f.write("=" * 60 + "\n\n")
                        f.write(all_qa)
                    output_paths["qa_answers"] = qa_path

                ps["output_paths"] = output_paths

                with st.spinner("Updating memory..."):
                    new_state = pipeline.run_phase6(ps)
                    ss[_slot_key(slot, "pipeline_state")] = new_state
                    ps = new_state

                mem_update = ps.get("memory_update", {})
                if mem_update.get("updates"):
                    update_memory(mem_update["updates"])
                if mem_update.get("questions_asked"):
                    existing = _load_memory()
                    already  = existing.get("questions_already_asked", [])
                    new_qs   = [q for q in mem_update["questions_asked"] if q not in already]
                    if new_qs:
                        update_memory({"questions_already_asked": already + new_qs})

                ss[_slot_key(slot, "step")] = "final_done"
                _clear_session(slot)
                st.rerun()

    # ── STEP 3: Final done ───────────────────────────────────────────────
    elif ss[_slot_key(slot, "step")] == "final_done":
        analysis = ps.get("analysis", {})
        company  = analysis.get("company", "Unknown")
        role     = analysis.get("role", "Unknown")
        sector   = analysis.get("sector", "ngo_philanthropy")
        layout   = ps.get("layout", {})

        output_paths = ps.get("output_paths", {})
        if output_paths:
            st.success("Documents saved successfully.")
            if "resume" in output_paths:
                st.markdown(f"**Resume:** `{output_paths['resume']}`")
            if "cover_letter" in output_paths:
                st.markdown(f"**Cover letter:** `{output_paths['cover_letter']}`")
            if "application_answers" in output_paths:
                st.markdown(f"**App answers:** `{output_paths['application_answers']}`")
            if "qa_answers" in output_paths:
                st.markdown(f"**Q&A log:** `{output_paths['qa_answers']}`")
        else:
            st.warning("No output files were generated.")

        ats_results = ps.get("ats_results", [])
        if ats_results:
            with st.expander("ATS Compatibility Check"):
                for r in ats_results:
                    icon = {"pass": "pass", "warn": "warning", "fail": "error"}[r["status"]]
                    getattr(st, icon if icon != "pass" else "success")(
                        f"**{r['check']}**: {r['detail']}"
                    )

        fmt_report = ps.get("formatting_report")
        if fmt_report:
            with st.expander("Formatting Report"):
                c1, c2 = st.columns(2)
                with c1:
                    st.metric("Estimated Pages", fmt_report.get("estimated_pages", "?"))
                    name_ok = fmt_report.get("has_name_block", False)
                    st.metric("Name Block", "Detected" if name_ok else "Missing")
                with c2:
                    st.metric("Paragraphs", fmt_report.get("paragraph_count", "?"))
                    st.metric("Headings", fmt_report.get("heading_count", "?"))
                st.markdown(f"**Fonts:** {', '.join(fmt_report.get('fonts_used', [])) or 'default'}")
                st.markdown(f"**Font sizes:** {', '.join(str(s) for s in fmt_report.get('font_sizes_pt', []))}")
                if fmt_report.get("margins"):
                    m = fmt_report["margins"]
                    st.markdown(
                        f"**Margins:** {m.get('top', '?')}\" T, {m.get('bottom', '?')}\" B, "
                        f"{m.get('left', '?')}\" L, {m.get('right', '?')}\" R"
                    )
                for w in fmt_report.get("warnings", []):
                    st.warning(w)

        st.info(f"**{company}** — {role} &nbsp;|&nbsp; Sector: `{sector}`")

        st.subheader("Final Resume")
        final_resume = ps.get("final_resume", {})
        st.text_area(
            "final_resume",
            value=final_resume.get("text", "(not available)"),
            height=420,
            disabled=True,
            label_visibility="collapsed",
            key=f"{slot}_final_resume",
        )

        st.subheader("Final Cover Letter")
        final_cover = ps.get("final_cover_letter", {})
        st.text_area(
            "final_cover_letter",
            value=final_cover.get("text", "(not available)"),
            height=300,
            disabled=True,
            label_visibility="collapsed",
            key=f"{slot}_final_cover",
        )

        app_answers = ps.get("app_question_answers", [])
        if app_answers:
            st.subheader("Application Question Answers")
            st.caption("Copy-paste these into the application form.")
            for i, aq in enumerate(app_answers):
                st.markdown(f"**Q{i+1}:** {aq.get('question', '')}")
                edited = ss.get(f"{slot}_app_answer_{i}", aq.get("answer", ""))
                st.text_area(
                    f"final_app_answer_{i}",
                    value=edited,
                    height=150,
                    label_visibility="collapsed",
                    key=f"{slot}_final_app_answer_{i}",
                )

        mem_update = ps.get("memory_update", {})
        if mem_update.get("updates"):
            with st.expander("Memory updates stored"):
                st.json(mem_update["updates"])

        st.divider()
        st.subheader("Feedback")
        feedback = st.text_area(
            "What would you change?",
            placeholder="e.g. 'Make the summary more concise', 'Emphasize leadership more in the second role'...",
            height=120,
            key=f"{slot}_user_feedback_input",
        )

        col_revise, col_new = st.columns([2, 1])
        with col_revise:
            if st.button("Revise with Feedback", type="primary", use_container_width=True,
                          key=f"{slot}_revise_btn"):
                if not feedback.strip():
                    st.error("Please provide some feedback before revising.")
                else:
                    ps["user_feedback"] = feedback.strip()
                    try:
                        with st.spinner("Revising based on your feedback..."):
                            new_state = pipeline.run_phase5(ps)
                            ss[_slot_key(slot, "pipeline_state")] = new_state
                            ps = new_state
                    except Exception as exc:
                        st.error(f"Revision failed: {exc}")
                        st.stop()

                    output_paths = {}
                    final_resume = ps.get("final_resume", {})
                    final_cover  = ps.get("final_cover_letter", {})

                    if final_resume.get("text"):
                        result = write_docx(
                            final_resume["text"], company, role, "resume",
                            sector=sector, layout=layout or None,
                        )
                        output_paths["resume"] = result["path"]
                        ps["ats_results"]       = ats_check(result["path"])
                        ps["formatting_report"] = verify_docx(result["path"])

                    if final_cover.get("text"):
                        result = write_docx(
                            final_cover["text"], company, role, "cover_letter",
                            sector=sector, layout=layout or None,
                        )
                        output_paths["cover_letter"] = result["path"]

                    old_paths = ps.get("output_paths", {})
                    if "application_answers" in old_paths:
                        output_paths["application_answers"] = old_paths["application_answers"]
                    if "qa_answers" in old_paths:
                        output_paths["qa_answers"] = old_paths["qa_answers"]

                    ps["output_paths"]  = output_paths
                    ps["user_feedback"] = ""
                    ss[_slot_key(slot, "pipeline_state")] = ps
                    st.rerun()

        with col_new:
            if st.button("Start New Application", use_container_width=True,
                          key=f"{slot}_new_app_btn"):
                _reset()
                st.rerun()


# ---------------------------------------------------------------------------
# Streamlit app
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Resume Builder", layout="wide")
st.title("Resume Builder")

# Build dynamic tab labels
tab_labels = [_slot_label(s) for s in _SLOTS] + ["App Questions", "Design Preview"]
tabs = st.tabs(tab_labels)

tab1, tab2, tab3, tab4, tab_appq, tab_design = tabs

# ── App slots ─────────────────────────────────────────────────────────────
with tab1:
    _render_builder("app1")

with tab2:
    _render_builder("app2")

with tab3:
    _render_builder("app3")

with tab4:
    _render_builder("app4")

# ── Standalone App Questions tab ──────────────────────────────────────────
with tab_appq:
    st.subheader("Application Questions")
    st.caption(
        "Use this tab when application questions appear after you have already "
        "finalized or iterated a resume. Select the completed application to load "
        "its full context, paste the questions, and generate answers."
    )

    # Build list of completed applications from output/
    completed_apps = []
    if os.path.isdir(OUTPUT_DIR):
        for folder in sorted(os.listdir(OUTPUT_DIR)):
            folder_path = os.path.join(OUTPUT_DIR, folder)
            if os.path.isdir(folder_path):
                resume_path = os.path.join(folder_path, "resume.docx")
                if os.path.exists(resume_path):
                    completed_apps.append(folder)

    # Also include active slot sessions that are in drafts_review or final_done
    active_options = []
    for s in _SLOTS:
        ps_check = st.session_state.get(_slot_key(s, "pipeline_state"), {})
        step_check = st.session_state.get(_slot_key(s, "step"), "input")
        if ps_check and step_check in ("drafts_review", "final_done"):
            analysis_check = ps_check.get("analysis", {})
            label = f"[Active] {analysis_check.get('company', s)} — {analysis_check.get('role', '')}"
            active_options.append((label, s, ps_check))

    if not completed_apps and not active_options:
        st.info("No completed applications found yet. Run at least one application first.")
    else:
        source_options = ["— select —"]
        for label, slot_id, _ in active_options:
            source_options.append(label)
        for folder in completed_apps:
            source_options.append(folder)

        selected_source = st.selectbox(
            "Select application context to use",
            options=source_options,
            key="appq_source_select",
        )

        if selected_source != "— select —":
            # Resolve pipeline state from selection
            appq_ps = None

            for label, slot_id, slot_ps in active_options:
                if selected_source == label:
                    appq_ps = slot_ps.copy()
                    break

            if appq_ps is None:
                # Load from output folder — reconstruct minimal state from saved files
                folder_path = os.path.join(OUTPUT_DIR, selected_source)
                resume_path = os.path.join(folder_path, "resume.docx")
                cover_path  = os.path.join(folder_path, "cover_letter.docx")
                # Try loading a cached session for this folder
                cache_candidates = [
                    f for f in os.listdir(MEMORY_DIR)
                    if f.startswith("session_cache_") and f.endswith(".json")
                ] if os.path.isdir(MEMORY_DIR) else []

                appq_ps = {
                    "job_description": "",
                    "resume_content": read_all_resumes(),
                    "memory_json": _load_memory(),
                    "memory_md": read_memory_md_files(),
                }
                # Parse company/role from folder name
                parts = selected_source.split("_")
                appq_ps["analysis"] = {"company": selected_source, "role": "", "sector": "ngo_philanthropy"}

                # Load docx text if available
                try:
                    from src.reader import _read_docx
                    if os.path.exists(resume_path):
                        appq_ps["draft_resume"] = {"text": _read_docx(resume_path)}
                    if os.path.exists(cover_path):
                        appq_ps["draft_cover_letter"] = {"text": _read_docx(cover_path)}
                except Exception:
                    pass

                st.info(
                    "Loaded from saved output folder. For best results, use an **active** "
                    "slot where the full pipeline context (strategy, iteration Q&A) is still in memory."
                )

            # Show context summary
            _aq_analysis = appq_ps.get("analysis", {})
            st.markdown(
                f"**Context:** {_aq_analysis.get('company', '?')} — "
                f"{_aq_analysis.get('role', '?')} &nbsp;|&nbsp; "
                f"Sector: `{_aq_analysis.get('sector', '?')}`"
            )
            if appq_ps.get("all_answers"):
                st.caption(f"Iteration Q&A included: {len(appq_ps['all_answers'])} chars of context")

            st.divider()

            # Paste questions
            appq_questions = st.text_area(
                "Paste application questions here",
                height=200,
                placeholder=(
                    "e.g.\n"
                    "1. Why do you want to work at [Company]? (max 300 words)\n"
                    "2. Describe a time you led a team through ambiguity.\n"
                    "3. What is your approach to stakeholder engagement?"
                ),
                key="appq_questions_input",
            )

            if st.button("Generate Answers", type="primary", key="appq_generate_btn", use_container_width=True):
                if not appq_questions.strip():
                    st.error("Please paste at least one question.")
                else:
                    appq_ps["application_questions"] = appq_questions.strip()
                    try:
                        with st.spinner("Drafting answers..."):
                            result_state = pipeline.run_app_questions(appq_ps)
                        st.session_state["appq_result"] = result_state
                    except Exception as exc:
                        st.error(f"Failed: {exc}")

            # Show results
            if "appq_result" in st.session_state:
                result = st.session_state["appq_result"]
                answers = result.get("app_question_answers", [])
                clarifying = result.get("app_clarifying_questions", [])

                if clarifying:
                    st.warning("The agent needs more info to answer some questions:")
                    for cq in clarifying:
                        st.markdown(f"- {cq}")
                    extra_info = st.text_area(
                        "Provide additional context (optional)",
                        height=100,
                        key="appq_extra_info",
                    )
                    if st.button("Regenerate with extra context", key="appq_regen_btn"):
                        appq_ps["application_questions"] = appq_questions.strip()
                        if extra_info.strip():
                            appq_ps["all_answers"] = (appq_ps.get("all_answers", "") + "\n\n" + extra_info).strip()
                        try:
                            with st.spinner("Regenerating answers..."):
                                result_state = pipeline.run_app_questions(appq_ps)
                            st.session_state["appq_result"] = result_state
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Failed: {exc}")

                if answers:
                    st.subheader("Drafted Answers")
                    for i, aq in enumerate(answers):
                        st.markdown(f"**Q{i+1}:** {aq.get('question', '')}")
                        if aq.get("word_count"):
                            st.caption(f"Word count: {aq['word_count']}")
                        st.text_area(
                            f"appq_answer_{i}",
                            value=aq.get("answer", ""),
                            height=150,
                            key=f"appq_answer_display_{i}",
                            label_visibility="collapsed",
                        )
                        if aq.get("assumptions_made"):
                            st.caption(f"Assumptions: {', '.join(aq['assumptions_made'])}")

                    # Save to output folder
                    if selected_source != "— select —" and selected_source not in [l for l, _, _ in active_options]:
                        folder_path = os.path.join(OUTPUT_DIR, selected_source)
                    else:
                        folder_path = None
                        for label, slot_id, _ in active_options:
                            if selected_source == label:
                                slot_ps_check = ss.get(_slot_key(slot_id, "pipeline_state"), {})
                                an = slot_ps_check.get("analysis", {})
                                folder_path = _output_folder_for(an.get("company", "unknown"), an.get("role", "unknown"))
                                break

                    if folder_path and st.button("Save answers to output folder", key="appq_save_btn"):
                        os.makedirs(folder_path, exist_ok=True)
                        save_path = os.path.join(folder_path, "application_answers.txt")
                        with open(save_path, "w", encoding="utf-8") as f:
                            for i, aq in enumerate(answers):
                                f.write(f"Q{i+1}: {aq.get('question', '')}\n\n")
                                f.write(f"{aq.get('answer', '')}\n\n")
                                f.write("---\n\n")
                        st.success(f"Saved to `{save_path}`")

# ── Design Preview tab ────────────────────────────────────────────────────
with tab_design:
    st.subheader("Resume design preview")
    st.caption("Fictional data — review fonts, spacing, and layout before running a real application.")

    sector_choice = st.selectbox(
        "Sector format",
        options=["ngo_philanthropy", "consulting", "clean_energy"],
        format_func=lambda s: {
            "ngo_philanthropy": "NGO / Philanthropy",
            "consulting": "Consulting",
            "clean_energy": "Clean Energy",
        }[s],
    )
    preview_fmt = dict(_SECTOR_FORMATS[sector_choice])

    # Allow pulling layout from any active slot
    active_slots = [
        s for s in _SLOTS
        if st.session_state.get(_slot_key(s, "pipeline_state"), {}).get("layout")
    ]
    if active_slots:
        layout_source = st.selectbox(
            "Use layout from",
            options=["sector defaults"] + active_slots,
            format_func=lambda x: x if x == "sector defaults" else _slot_label(x),
        )
        if layout_source != "sector defaults":
            layout = st.session_state[_slot_key(layout_source, "pipeline_state")]["layout"]
            for key in (
                "body_pt", "header_name_pt", "section_heading_pt",
                "top_margin", "bottom_margin", "left_margin", "right_margin",
                "line_spacing_pt", "space_after_pt", "bullet_indent",
                "heading_space_before_pt",
            ):
                if key in layout and isinstance(layout[key], (int, float)):
                    preview_fmt[key] = layout[key]
            for key in ("accent_color", "heading_underline", "name_color", "divider_style", "font_family"):
                if key in layout:
                    preview_fmt[key] = layout[key]
            st.info(f"Showing layout from **{_slot_label(layout_source)}**.")

    ff = preview_fmt.get("font_family", "Calibri")
    st.markdown(
        f"**Font:** {ff} &nbsp;|&nbsp; **Body:** {preview_fmt['body_pt']}pt &nbsp;|&nbsp; "
        f"**Name header:** {preview_fmt['header_name_pt']}pt &nbsp;|&nbsp; "
        f"**Section heading:** {preview_fmt['section_heading_pt']}pt &nbsp;|&nbsp; "
        f"**Margins:** {preview_fmt['left_margin']}\" L/R, {preview_fmt['top_margin']}\" T/B &nbsp;|&nbsp; "
        f"**Line spacing:** {preview_fmt['line_spacing_pt']}pt"
    )
    if preview_fmt.get("accent_color"):
        c = preview_fmt["accent_color"]
        st.markdown(
            f"**Accent:** <span style='color:{c};font-weight:bold;'>{c}</span> &nbsp;|&nbsp; "
            f"**Underlines:** {'Yes' if preview_fmt.get('heading_underline') else 'No'} &nbsp;|&nbsp; "
            f"**Dividers:** {preview_fmt.get('divider_style', 'none')}",
            unsafe_allow_html=True,
        )
    components.html(_resume_to_html(_FICTIONAL_RESUME, preview_fmt), height=1100, scrolling=True)

# ── Feedback Learning sidebar ──────────────────────────────────────────────
with st.sidebar:
    st.markdown("---")
    st.subheader("Aprendizaje de feedback")
    st.caption(
        "Deja tus versiones editadas en la carpeta `feedback/` "
        "con nombres como `resume_GIIN.docx` o `cover_letter_LFC.docx`. "
        "El sistema las compara con los drafts originales y aprende tu estilo."
    )

    memory_for_feedback = _load_memory()
    already_analyzed = get_already_analyzed(memory_for_feedback)

    pairs = pair_feedback_with_output()
    new_pairs = [
        p for p in pairs
        if p["company_tag"] not in already_analyzed
    ]

    if not pairs:
        st.info("No hay archivos en la carpeta `feedback/` todavía.")
    elif not new_pairs:
        st.success(f"Todo analizado. {len(pairs)} archivos ya procesados.")
        if st.button("Ver archivos procesados"):
            st.write(already_analyzed)
    else:
        st.info(f"{len(new_pairs)} archivo(s) nuevo(s) para analizar.")
        for p in new_pairs:
            match_info = f"→ {p['folder']}" if p["folder"] != "(unmatched)" else "⚠ sin match en output/"
            st.markdown(f"- `{p['company_tag']}` ({p['type']}) {match_info}")

        if st.button("Analizar feedback y aprender estilo"):
            with st.spinner("Analizando diferencias con tus edits..."):
                try:
                    analyst = FeedbackAnalyst()
                    state = {
                        "feedback_pairs": new_pairs,
                        "already_analyzed": already_analyzed,
                    }
                    result_state = analyst.run(state)
                    learnings = result_state.get("feedback_learnings", {})

                    if learnings:
                        # Merge learnings into memory.json
                        # Track analyzed file tags
                        new_tags = [p["company_tag"] for p in new_pairs]
                        learnings["feedback_analyzed_files"] = already_analyzed + new_tags
                        update_memory(learnings)
                        st.success("Aprendizaje guardado en memory.json.")
                        if learnings.get("human_edits_patterns"):
                            st.markdown("**Patrones aprendidos:**")
                            for item in learnings["human_edits_patterns"]:
                                st.markdown(f"- {item}")
                        if learnings.get("style_preferences"):
                            st.markdown("**Preferencias de estilo:**")
                            for item in learnings["style_preferences"]:
                                st.markdown(f"- {item}")
                        if learnings.get("recurring_fixes"):
                            st.markdown("**Correcciones recurrentes:**")
                            for item in learnings["recurring_fixes"]:
                                st.markdown(f"- {item}")
                    else:
                        st.warning("El agente no encontró patrones nuevos para guardar.")
                except Exception as e:
                    st.error(f"Error en el análisis: {e}")
