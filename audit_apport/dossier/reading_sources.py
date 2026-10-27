"""Public retrieval and page/line evidence, with no semantic completion claim."""
from __future__ import annotations
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import textwrap
import unicodedata
import urllib.parse
import urllib.request

from .io import digest, require, sha

MAX_BYTES = 30_000_000
WALLS = ("this is a preview of subscription content", "access through your institution",
         "verify you are human", "checking your browser", "enable javascript and cookies to continue")
TERMS = {
    "C1": ("theorem", "proposition", "assumption", "bernstein", "refinement", "convergence", "consistency",
           "derivative", "mesh", "gamma", "margin", "bid", "ask", "local volatility"),
    "C2": ("feasible", "infeasible", "feasibility", "forward", "backward", "intersection", "linear program",
           "bound", "farkas", "discrete local", "arbitrage", "spread"),
    "C3": ("time step", "time-step", "crank", "nicolson", "midpoint", "stability", "implicit", "explicit",
           "forward", "backward", "gamma", "bound", "compatibility")}
STOP = {"the", "and", "for", "with", "under", "from", "of", "a", "an", "in", "to", "on", "at"}


def url_ok(url):
    value = urllib.parse.urlsplit(url)
    require(value.scheme == "https" and value.hostname and not value.username and not value.password,
            "Full-text retrieval needs a public HTTPS URL without embedded credentials")
    require(value.hostname not in {"localhost", "127.0.0.1", "::1"}, "Not a public full-text URL")
    return url


def download(url, timeout=15):
    url_ok(url)
    request = urllib.request.Request(url, headers={"User-Agent": "DupireReadingAudit/0.5 (academic research)"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        final = response.geturl()
        url_ok(final)
        raw = response.read(MAX_BYTES+1)
        require(len(raw) <= MAX_BYTES, "Document exceeds the 30 MB download limit")
        return raw, {"requested_url": url, "final_url": final, "content_type": response.headers.get("Content-Type", ""),
                     "raw_sha256": hashlib.sha256(raw).hexdigest()}


def crossref_routes(doi, timeout=15):
    url = "https://api.crossref.org/works/"+urllib.parse.quote(doi, safe="/")
    raw, receipt = download(url, timeout)
    message = json.loads(raw)["message"]
    require(message["DOI"].lower() == doi.lower(), "Crossref returned another work")
    urls = [item["URL"] for item in message.get("link", []) if
            item.get("content-type") in {"application/pdf", "text/html", "text/xml"} and item["URL"].startswith("https://")]
    return urls, receipt


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.skipped = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript", "svg"}:
            self.skipped += 1
        if tag in {"p", "h1", "h2", "h3", "section", "li", "br"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "svg"}:
            self.skipped = max(0, self.skipped-1)

    def handle_data(self, data):
        if not self.skipped:
            self.parts.append(data)


def lines_of(text):
    text = unicodedata.normalize("NFKC", text).replace("\x00", "")
    lines = []
    for line in text.splitlines():
        line = " ".join(line.split())
        if line:
            lines.extend(textwrap.wrap(line, width=120, break_long_words=False, break_on_hyphens=False) or [line])
    return lines


def extract(path, max_pages=1500):
    path = Path(path)
    with path.open("rb") as stream:
        head = stream.read(1024)
    errors, pages = [], []
    if head.lstrip().startswith(b"%PDF-"):
        try:
            import pypdf
        except ImportError as error:
            raise ValueError('PDF extraction requires: python -m pip install "pypdf>=5,<7"') from error
        reader = pypdf.PdfReader(path, strict=False)
        require(not reader.is_encrypted, "Encrypted PDF: supply an accessible copy")
        require(len(reader.pages) <= max_pages, "PDF exceeds the declared page budget")
        for i, page in enumerate(reader.pages, 1):
            try:
                content = page.get_contents()
                require(content is None or len(content.get_data()) <= 8_000_000, "Page content stream too large")
                text = page.extract_text() or ""
                require(len(text) <= 1_000_000, "Extracted page unexpectedly large")
            except Exception as error:
                errors.append({"page": i, "error": str(error)[:350]})
                text = ""
            pages.append({"page": i, "lines": lines_of(text)})
        kind, extractor = "pdf", "pypdf "+pypdf.__version__
    else:
        raw = path.read_bytes()
        require(len(raw) <= MAX_BYTES, "Text document exceeds extraction budget")
        text = raw.decode("utf-8-sig", errors="replace")
        require(text.count('\ufffd') <= max(5, len(text)//1000) and text.count('\x00') <= max(2, len(text)//1000),
                "Unsupported binary/text encoding; supply a PDF or UTF-8 scholarly text")
        if re.search(r"<(?:!doctype|html|body|article)\b", text, re.I):
            parser = VisibleText(); parser.feed(text)
            text, kind = " ".join(parser.parts), "html"
        else:
            kind = "text"
        all_lines = lines_of(text)
        # HTML/text locations are explicitly virtual pages; never printed PDF page numbers.
        pages = [{"page": i//80+1, "lines": all_lines[i:i+80]} for i in range(0, len(all_lines), 80)]
        pages = pages or [{"page": 1, "lines": []}]
        extractor = "stdlib-visible-text-v1"
    for page in pages:
        page["sha256"] = digest({"page": page["page"], "lines": page["lines"]})
    text = "\n".join(line for page in pages for line in page["lines"])
    wall = any(marker in text.lower() for marker in WALLS)
    body_words = len(text.split())
    html_metadata = kind == "html" and ("introduction" not in text.lower() or body_words < 1500)
    status = ("preview_or_access_wall" if wall else "html_metadata_or_excerpt" if html_metadata else
              "ocr_or_text_recovery_needed" if body_words < 100 else
              "text_extraction_partial" if errors else "text_extracted_extent_unconfirmed")
    return {"format": "dupire-extracted-source-v1", "source_sha256": sha(path), "source_kind": kind,
            "location_kind": "pdf_physical_page" if kind == "pdf" else "virtual_text_page_80_lines",
            "extractor": extractor, "page_count": len(pages), "word_count": body_words,
            "pages": pages, "extraction_errors": errors, "status": status,
            "full_text_extent_auto_verified": False}


def identity_hint(title, extracted):
    tokens = set(re.findall(r"[a-z0-9]+", title.lower()))-STOP
    first = " ".join(line for page in extracted["pages"][:3] for line in page["lines"]).lower()
    found = set(re.findall(r"[a-z0-9]+", first))
    share = len(tokens & found)/max(1, len(tokens))
    return {"title_token_overlap": round(share, 4), "identity_auto_verified": False,
            "hint": "title_match_candidate" if share >= .55 else "manual_identity_check_required"}


def passages(extracted):
    blocks = []
    for page in extracted["pages"]:
        lines = page["lines"]
        for start in range(0, len(lines), 12):
            stop = min(start+16, len(lines))
            body = "\n".join(lines[start:stop])
            if not body.strip():
                continue
            blocks.append({"id": f"p{page['page']:04d}:l{start+1:04d}-{stop:04d}", "page": page["page"],
                           "line_start": start+1, "line_end": stop, "sha256": hashlib.sha256(body.encode()).hexdigest(),
                           "text": body})
    return blocks


def select_passages(extracted, claim_id, max_blocks=8, max_chars=22000):
    ranked = []
    for index, block in enumerate(passages(extracted)):
        text = block["text"].lower()
        score = sum(min(text.count(word), 3) for word in TERMS[claim_id])
        if re.search(r"\b(theorem|proposition|lemma|assumption|definition)\b", text):
            score += 3
        ranked.append((-score, index, block))
    chosen, budget = [], 0
    for score, index, block in sorted(ranked):
        if len(chosen) >= max_blocks:
            break
        if budget+len(block["text"]) > max_chars:
            continue
        chosen.append(block); budget += len(block["text"])
    return sorted(chosen, key=lambda b: (b["page"], b["line_start"]))
