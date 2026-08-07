"""
Text normalisation shared by training and inference.

Training labels are produced per-sentence, so the sentence splitter used to build
the dataset MUST be the same one used at prediction time — otherwise the model
sees differently-shaped inputs than it was fitted on.
"""
import re
from typing import List, Tuple

# Clause numbering that SEBI circulars use: "3.", "3.1", "4.2.1", "(a)", "(iv)"
CLAUSE_NUM_RE = re.compile(r'^\s*(?:\(?\d+(?:\.\d+)*\)?[.)]?|\([a-z]{1,3}\)|\([ivxl]{1,5}\))\s+')

# Abbreviations that must not end a sentence.
_ABBREV = {
    "no", "nos", "vs", "viz", "etc", "i.e", "e.g", "sec", "cl", "pvt", "ltd",
    "sr", "dr", "mr", "ms", "hon", "para", "fig", "rs",
}

_SENT_END_RE = re.compile(r'(?<=[.!?;])\s+')


def clean_text(text: str) -> str:
    """Collapse PDF artefacts: hard-wrapped lines, page numbers, repeated spaces."""
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Drop standalone page-number lines ("Page 3 of 12", "3")
    text = re.sub(r'(?m)^\s*(?:page\s+)?\d+(?:\s+of\s+\d+)?\s*$', '', text, flags=re.IGNORECASE)
    # Re-join words split across a line break with a hyphen
    text = re.sub(r'(\w)-\n(\w)', r'\1\2', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


# A heading is short, has few words and does not read as a sentence.
_HEADING_LINE_RE = re.compile(
    r'^(?:\d+(?:\.\d+)*\.?\s+)?[A-Z][A-Za-z][A-Za-z ,&/()\'-]{3,70}$'
)


def segment_blocks(text: str) -> List[Tuple[str, str]]:
    """
    Split a document into logical blocks: [(kind, text), …] with kind in
    {"heading", "clause", "text"}.

    Works on both blank-line-separated text and the run-together line stream that
    pdfplumber produces from a PDF, because a new block is started by a clause
    number or a heading line — not only by a blank line. Training text and
    extracted PDF text therefore segment identically.
    """
    blocks: List[Tuple[str, str]] = []
    buf: List[str] = []
    kind = "text"

    def flush():
        nonlocal buf, kind
        joined = " ".join(" ".join(buf).split())
        if joined:
            blocks.append((kind, joined))
        buf, kind = [], "text"

    for raw in clean_text(text).split("\n"):
        line = raw.strip()
        if not line:
            flush()
            continue

        is_numbered = bool(CLAUSE_NUM_RE.match(line))
        words = line.split()
        looks_like_heading = (
            len(line) <= 80
            and len(words) <= 10
            and not line.endswith(('.', ';', ':'))
            and _HEADING_LINE_RE.match(line) is not None
        )

        if looks_like_heading:
            flush()
            blocks.append(("heading", line))
            continue
        if is_numbered:
            flush()
            kind = "clause"
        buf.append(line)

    flush()
    return blocks


def split_sentences(text: str) -> List[str]:
    """
    Split regulatory text into sentences.

    Block boundaries are hard boundaries first (a numbered clause is a unit even
    when it has no full stop), then each block is split on end-punctuation while
    protecting abbreviations and decimal clause numbers.
    """
    sentences: List[str] = []
    for _kind, para in segment_blocks(text):
        if not para:
            continue
        # Protect decimals and clause numbers from the sentence splitter
        protected = re.sub(r'(?<=\d)\.(?=\d)', '<DOT>', para)
        for raw in _SENT_END_RE.split(protected):
            s = raw.replace('<DOT>', '.').strip()
            if not s:
                continue
            # Re-attach fragments that were cut after an abbreviation
            last_word = s.rstrip('.').split(' ')[-1].lower() if s else ""
            if sentences and last_word in _ABBREV:
                sentences[-1] = sentences[-1] + " " + s
            else:
                sentences.append(s)
    return [s for s in sentences if len(s) > 2]


def strip_clause_number(sentence: str) -> Tuple[str, str]:
    """Return (clause_number, remaining_text). Number is '' when absent."""
    m = CLAUSE_NUM_RE.match(sentence)
    if not m:
        return "", sentence.strip()
    return m.group(0).strip().rstrip('.)'), sentence[m.end():].strip()


def is_boilerplate(sentence: str) -> bool:
    """Letterhead, addresses, signatures and legal footers carry no obligation."""
    s = sentence.strip()
    low = s.lower()
    if len(s) < 25:
        return True
    if re.match(r'^(yours faithfully|yours sincerely|encl|copy to|to,?$|sir/madam|dear sir)', low):
        return True
    if 'securities and exchange board of india' in low and len(s) < 80:
        return True
    if re.match(r'^(annexure|appendix|schedule|table)\b', low) and len(s) < 60:
        return True
    # Mostly digits / punctuation (reference numbers, tables of figures)
    letters = sum(c.isalpha() for c in s)
    return letters < len(s) * 0.5
