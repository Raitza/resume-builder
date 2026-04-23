import os
import glob
from docx import Document

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILES_DIR = os.path.join(BASE_DIR, "profiles")
RESUMES_DIR = os.path.join(BASE_DIR, "resumes")
MEMORY_DIR = os.path.join(BASE_DIR, "memory")


def _read_docx(path: str) -> str:
    doc = Document(path)
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _read_file(path: str) -> str:
    if path.endswith(".docx"):
        return _read_docx(path)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def read_profile(filename: str) -> str:
    path = os.path.join(PROFILES_DIR, filename)
    return _read_file(path)


def read_resume(filename: str) -> str:
    path = os.path.join(RESUMES_DIR, filename)
    return _read_file(path)


def read_all_resumes() -> str:
    """Read every .docx in /resumes/ and return combined plain text."""
    pattern = os.path.join(RESUMES_DIR, "*.docx")
    files = sorted(glob.glob(pattern))
    if not files:
        raise FileNotFoundError(f"No .docx files found in {RESUMES_DIR}")
    sections = []
    for filepath in files:
        name = os.path.basename(filepath)
        content = _read_docx(filepath).strip()
        if content:
            sections.append(f"### {name}\n{content}")
    return "\n\n".join(sections)


def read_memory_md_files() -> str:
    pattern = os.path.join(MEMORY_DIR, "*.md")
    files = sorted(glob.glob(pattern))
    sections = []
    for filepath in files:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if content:
            name = os.path.basename(filepath)
            sections.append(f"### {name}\n{content}")
    return "\n\n".join(sections)
