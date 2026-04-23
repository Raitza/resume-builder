"""Reads feedback/ and output/ folders and pairs files for style-diff analysis."""

from __future__ import annotations

import os
import glob

from src.reader import _read_docx

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEEDBACK_DIR = os.path.join(BASE_DIR, "feedback")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")


def _parse_feedback_filename(filename: str) -> tuple[str, str]:
    """Extract (doc_type, company_tag) from a feedback filename.

    Accepts cover letter prefixes: cover_letter, coverletter, cover letter, coverle
    Accepts resume prefix: resume
    """
    name = filename.lower().replace(".docx", "").strip()

    _CL_PREFIXES = ("cover_letter", "cover letter", "coverletter", "coverle")
    if any(name.startswith(p) for p in _CL_PREFIXES):
        doc_type = "cover_letter"
        for p in _CL_PREFIXES:
            name = name.replace(p, "", 1)
    elif name.startswith("resume"):
        doc_type = "resume"
        name = name.replace("resume", "", 1)
    else:
        doc_type = "unknown"

    tag = name.strip("_ ").strip()
    return doc_type, tag


def _normalize(text: str) -> str:
    """Lowercase and strip punctuation/spaces for fuzzy matching."""
    import re
    return re.sub(r"[^a-z0-9]", "", text.lower())


def read_feedback_files() -> list[dict]:
    """Return list of dicts {filename, type, company_tag, text} from feedback/."""
    results = []
    pattern = os.path.join(FEEDBACK_DIR, "*.docx")
    for filepath in sorted(glob.glob(pattern)):
        filename = os.path.basename(filepath)
        doc_type, company_tag = _parse_feedback_filename(filename)
        try:
            text = _read_docx(filepath)
        except Exception:
            text = ""
        if text.strip():
            results.append({
                "filename": filename,
                "type": doc_type,
                "company_tag": company_tag,
                "text": text,
            })
    return results


def read_output_files() -> list[dict]:
    """Return list of dicts {folder, type, text} for all output resume/cover_letter files."""
    results = []
    if not os.path.isdir(OUTPUT_DIR):
        return results
    for folder in sorted(os.listdir(OUTPUT_DIR)):
        folder_path = os.path.join(OUTPUT_DIR, folder)
        if not os.path.isdir(folder_path):
            continue
        for doc_type, filename in [
            ("resume", "resume.docx"),
            ("cover_letter", "cover_letter.docx"),
        ]:
            filepath = os.path.join(folder_path, filename)
            if os.path.exists(filepath):
                try:
                    text = _read_docx(filepath)
                except Exception:
                    text = ""
                if text.strip():
                    results.append({
                        "folder": folder,
                        "type": doc_type,
                        "text": text,
                    })
    return results


def pair_feedback_with_output() -> list[dict]:
    """Match each feedback file with its corresponding output file.

    Matching is done by fuzzy-normalizing the company_tag against each output
    folder name (and known abbreviations within it). Returns list of dicts:
        {
            "company_tag": str,
            "folder": str,
            "type": "resume" | "cover_letter",
            "claude_output": str,   # what Claude generated
            "user_edited": str,     # what the user sent
        }
    Unmatched feedback files are included with claude_output = "" so the
    analyst can still extract style patterns from the user's version alone.
    """
    # Manual aliases: tag (normalized) → substring to search in output folder names
    _ALIASES: dict[str, str] = {
        "hep": "hewlett",
        "lfc": "lever",
    }

    feedback_files = read_feedback_files()
    output_files = read_output_files()

    # Index output by (type, folder)
    output_index: dict[tuple[str, str], str] = {
        (o["type"], o["folder"]): o["text"] for o in output_files
    }
    output_folders = [o["folder"] for o in output_files]

    pairs = []
    for fb in feedback_files:
        raw_tag = _normalize(fb["company_tag"])
        tag_norm = _ALIASES.get(raw_tag, raw_tag)
        best_folder: str | None = None

        # Try to find an output folder whose normalized name contains the tag,
        # OR whose name contains any token of the tag.
        for folder in output_folders:
            folder_norm = _normalize(folder)
            if tag_norm and (tag_norm in folder_norm or folder_norm.startswith(tag_norm)):
                best_folder = folder
                break

        # Fallback: check if any word token of the folder name contains the tag
        if best_folder is None and tag_norm:
            for folder in output_folders:
                folder_norm = _normalize(folder)
                if tag_norm in folder_norm:
                    best_folder = folder
                    break

        claude_output = ""
        if best_folder:
            claude_output = output_index.get((fb["type"], best_folder), "")

        pairs.append({
            "company_tag": fb["company_tag"],
            "folder": best_folder or "(unmatched)",
            "type": fb["type"],
            "claude_output": claude_output,
            "user_edited": fb["text"],
        })

    return pairs


def get_already_analyzed(memory: dict) -> list[str]:
    """Return list of feedback filenames already analyzed in a previous run."""
    return memory.get("feedback_analyzed_files", [])
