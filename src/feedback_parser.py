"""
Parse tracked changes and comments from a .docx feedback file.

python-docx does not expose revisions or comments through its high-level API,
so this module works directly against the underlying Open XML (lxml).
"""

from __future__ import annotations
from docx import Document
from lxml import etree

# Word XML namespaces
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W14 = "http://schemas.microsoft.com/office/word/2010/wordml"


def _tag(ns: str, local: str) -> str:
    return f"{{{ns}}}{local}"


def _inner_text(element) -> str:
    """Concatenate all w:t text nodes inside an element."""
    return "".join(
        node.text or ""
        for node in element.iter(_tag(W, "t"))
    )


def _parse_tracked_changes(body) -> list[dict]:
    changes = []

    for ins in body.iter(_tag(W, "ins")):
        text = _inner_text(ins)
        if text:
            changes.append({
                "type": "insertion",
                "author": ins.get(_tag(W, "author"), ""),
                "date": ins.get(_tag(W, "date"), ""),
                "text": text,
            })

    for delete in body.iter(_tag(W, "del")):
        # Deleted text lives in w:delText nodes
        text = "".join(
            node.text or ""
            for node in delete.iter(_tag(W, "delText"))
        )
        if text:
            changes.append({
                "type": "deletion",
                "author": delete.get(_tag(W, "author"), ""),
                "date": delete.get(_tag(W, "date"), ""),
                "text": text,
            })

    return changes


def _parse_comments(doc: Document) -> list[dict]:
    """Extract comments from word/comments.xml part."""
    comments = []
    try:
        comments_part = doc.part.package.part_related_by(
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments"
        )
    except KeyError:
        return comments

    root = etree.fromstring(comments_part.blob)
    for comment_el in root.iter(_tag(W, "comment")):
        text = _inner_text(comment_el)
        comments.append({
            "id": comment_el.get(_tag(W, "id"), ""),
            "author": comment_el.get(_tag(W, "author"), ""),
            "date": comment_el.get(_tag(W, "date"), ""),
            "text": text.strip(),
        })

    return comments


def _extract_raw_text(doc: Document) -> str:
    """Plain text of the document as accepted (insertions kept, deletions excluded)."""
    lines = []
    for para in doc.paragraphs:
        # Collect text from runs that are NOT inside a w:del element
        para_text_parts = []
        for node in para._p.iter(_tag(W, "t")):
            # Walk up to check if this t is inside a w:del
            parent = node.getparent()
            in_deletion = False
            while parent is not None:
                if parent.tag == _tag(W, "del"):
                    in_deletion = True
                    break
                parent = parent.getparent()
            if not in_deletion:
                para_text_parts.append(node.text or "")
        line = "".join(para_text_parts).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def parse_feedback(filepath: str) -> dict:
    """Return tracked changes, comments, and raw accepted text from a feedback .docx.

    Returns:
        {
            "tracked_changes": [{"type", "author", "date", "text"}, ...],
            "comments":        [{"id", "author", "date", "text"}, ...],
            "raw_text":        str,
        }
    """
    doc = Document(filepath)
    body = doc.element.body

    return {
        "tracked_changes": _parse_tracked_changes(body),
        "comments": _parse_comments(doc),
        "raw_text": _extract_raw_text(doc),
    }
