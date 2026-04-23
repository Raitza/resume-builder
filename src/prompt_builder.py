import json


def build_prompt(
    job_profile: str,
    resume_content: str,
    memory_content: dict,
    feedback_content: list,
    company: str,
    role: str,
) -> str:
    sections = []

    # --- Target ---
    sections.append(
        f"## TARGET APPLICATION\n"
        f"Company: {company}\n"
        f"Role: {role}"
    )

    # --- Job profile ---
    sections.append(
        f"## JOB DESCRIPTION\n{job_profile.strip()}"
    )

    # --- Resume ---
    sections.append(
        f"## CANDIDATE RESUME (source of truth — do not invent credentials)\n"
        f"{resume_content.strip()}"
    )

    # --- Structured memory ---
    if memory_content:
        sections.append(
            f"## ACCUMULATED MEMORY (preferences, corrections, candidate facts from prior runs)\n"
            f"{json.dumps(memory_content, indent=2)}"
        )

    # --- Markdown feedback files ---
    if feedback_content:
        combined = "\n\n---\n\n".join(f.strip() for f in feedback_content if f.strip())
        if combined:
            sections.append(
                f"## SESSION NOTES & FEEDBACK (strategic decisions and preferences from prior applications)\n"
                f"{combined}"
            )

    # --- Instructions ---
    sections.append(
        """## YOUR TASK — FOLLOW IN ORDER

### Step 1 — Analyze the job description
Extract: required skills, preferred skills, seniority signals, culture cues, ATS keywords, and what this organization truly values. Identify the one core tension this employer is trying to solve with this hire.

### Step 2 — Produce a first draft
Write a complete, tailored resume and cover letter for this specific role at this specific company. Apply all memory preferences, prior feedback, and session notes above.
- Resume: ATS-safe, quantified achievements, coherent career narrative, tailored summary (3–4 lines max), strong action verbs calibrated to sector and seniority. Length per memory preferences.
- Cover letter: Hook immediately (never "I am applying for…"). 3–5 paragraphs, one page max. Confident, elegant tone calibrated to the sector.

### Step 3 — Identify critical gaps
After drafting, list only gaps that would materially change the output if filled — missing quantified achievements for core requirements, unclear transitions, hard skills the JD requires that are not evidenced in any document. Skip gaps you can reasonably infer.

### Step 4 — Ask refinement questions
Present your draft, then ask your gap-filling questions. Rules:
- Check memory — never ask a question already asked in prior runs.
- Each question must be tied to a specific JD requirement or positioning decision.
- Frame as a strategic advisor, not a form. Be specific: name the project, the JD requirement, and why the answer matters.
- Example format: "The role emphasizes X. I don't have a concrete example of this in your materials. Can you recall a specific instance — project name, who you engaged, and what the outcome was?"

### Output format — REQUIRED
Structure your entire response using these exact markers. Do not include any text before the first marker.

---RESUME---
<complete resume text>

---COVER LETTER---
<complete cover letter text>

---QUESTIONS---
<your gap-filling questions, numbered>"""
    )

    return "\n\n".join(sections)
