"""
Resume Builder — orchestrator
Run: python main.py
"""

import json
import os
import sys
import textwrap

# Ensure src/ is importable from project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.reader import read_profile, read_all_resumes, read_memory_md_files
from src.prompt_builder import build_prompt
from src.claude_client import ask
from src.docx_writer import write_docx
from src.memory_updater import update_memory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SEPARATOR = "─" * 72


def _print_section(title: str, body: str) -> None:
    print(f"\n{SEPARATOR}")
    print(f"  {title}")
    print(SEPARATOR)
    print(body)


def _collect_input(prompt: str) -> str:
    value = input(prompt).strip()
    while not value:
        value = input(f"  (required) {prompt}").strip()
    return value


def _collect_answers() -> str:
    print("\nType your answers below.")
    print("When done, enter a single line containing only 'DONE' and press Enter.")
    lines = []
    while True:
        line = input()
        if line.strip().upper() == "DONE":
            break
        lines.append(line)
    return "\n".join(lines)


def _extract_section(text: str, marker: str) -> str:
    """Return text between marker and the next '---' separator or end of string."""
    lower = text.lower()
    start = lower.find(marker.lower())
    if start == -1:
        return ""
    start = text.find("\n", start) + 1          # skip the marker line itself
    end = text.find("\n---", start)
    return text[start:end].strip() if end != -1 else text[start:].strip()


def _build_refinement_prompt(
    first_draft: str,
    user_answers: str,
    company: str,
    role: str,
) -> str:
    return textwrap.dedent(f"""\
        ## CONTEXT
        Company: {company}
        Role: {role}

        ## FIRST DRAFT (your previous output)
        {first_draft}

        ## CANDIDATE'S ANSWERS TO YOUR QUESTIONS
        {user_answers}

        ## YOUR TASK
        Incorporate the candidate's answers and produce the final, polished output.
        Structure your response exactly as follows — use these exact markers:

        ---RESUME---
        <full resume text here>

        ---COVER LETTER---
        <full cover letter text here>

        ---OPTIMIZATION NOTES---
        <2–3 things prioritized for this application + 1–2 honest risks or gaps>

        ---MEMORY UPDATE---
        Output a JSON object of new candidate facts to store, using only keys that exist
        in memory.json: style_preferences, tone, recurring_fixes, questions_already_asked,
        candidate_facts (with sub-keys achievements, experiences, context),
        per_profile_type (with sub-keys consulting, clean_energy, ngo_philanthropy).
        Only include keys that actually have new information. Use empty dict {{}} if nothing new.
    """)


def _parse_final_output(response: str) -> tuple[str, str, str, dict]:
    """Return (resume, cover_letter, notes, memory_updates)."""
    resume = _extract_section(response, "---RESUME---")
    cover_letter = _extract_section(response, "---COVER LETTER---")
    notes = _extract_section(response, "---OPTIMIZATION NOTES---")

    memory_updates: dict = {}
    raw_memory = _extract_section(response, "---MEMORY UPDATE---")
    if raw_memory:
        # Strip markdown code fences if present
        raw_memory = raw_memory.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        try:
            memory_updates = json.loads(raw_memory)
        except json.JSONDecodeError:
            pass

    return resume, cover_letter, notes, memory_updates


# ---------------------------------------------------------------------------
# Main flow
# ---------------------------------------------------------------------------

def main() -> None:
    print("\n=== RESUME BUILDER ===\n")

    # 1. Collect inputs
    company = _collect_input("Company name: ")
    role = _collect_input("Role title: ")
    profile_file = _collect_input("Profile filename (from /profiles/): ")

    # 2. Load files
    print("\nLoading files…")
    try:
        job_profile = read_profile(profile_file)
    except FileNotFoundError:
        sys.exit(f"ERROR: profile file not found → profiles/{profile_file}")

    try:
        resume_content = read_all_resumes()
    except FileNotFoundError as e:
        sys.exit(f"ERROR: {e}")

    memory_md = read_memory_md_files()           # str
    feedback_content = [memory_md] if memory_md else []

    # memory.json is loaded inside claude_client automatically;
    # also load it here so prompt_builder can embed it
    memory_path = os.path.join(os.path.dirname(__file__), "memory", "memory.json")
    with open(memory_path, "r", encoding="utf-8") as f:
        memory_content = json.load(f)

    # 3. Build prompt
    prompt = build_prompt(
        job_profile=job_profile,
        resume_content=resume_content,
        memory_content=memory_content,
        feedback_content=feedback_content,
        company=company,
        role=role,
    )

    # 4 & 5. First call → draft + questions
    print("\nSending to Claude… (this may take a moment)")
    first_response = ask(prompt)
    _print_section("CLAUDE'S FIRST DRAFT + QUESTIONS", first_response)

    # 6. Collect user answers
    print(f"\n{SEPARATOR}")
    print("  ANSWER CLAUDE'S QUESTIONS")
    print(SEPARATOR)
    user_answers = _collect_answers()

    if not user_answers.strip():
        print("No answers provided — skipping refinement, saving first draft as-is.")
        final_response = first_response
    else:
        # 7. Refinement call
        refinement_prompt = _build_refinement_prompt(
            first_draft=first_response,
            user_answers=user_answers,
            company=company,
            role=role,
        )
        print("\nSending refinement to Claude…")
        final_response = ask(refinement_prompt)
        _print_section("FINAL OUTPUT", final_response)

    # 8. Parse and save docx files
    resume_text, cover_letter_text, notes, memory_updates = _parse_final_output(final_response)

    saved = []
    if resume_text:
        path = write_docx(resume_text, company, role, "resume")
        saved.append(f"  Resume       → {path}")
    else:
        print("WARNING: Could not parse resume section from final output.")

    if cover_letter_text:
        path = write_docx(cover_letter_text, company, role, "cover_letter")
        saved.append(f"  Cover letter → {path}")
    else:
        print("WARNING: Could not parse cover letter section from final output.")

    if saved:
        print(f"\n{SEPARATOR}")
        print("  FILES SAVED")
        print(SEPARATOR)
        for line in saved:
            print(line)

    if notes:
        _print_section("OPTIMIZATION NOTES", notes)

    # 9. Update memory
    if memory_updates:
        update_memory(memory_updates)
        print("\nMemory updated.")
    else:
        print("\nNo new memory to store.")


if __name__ == "__main__":
    main()
