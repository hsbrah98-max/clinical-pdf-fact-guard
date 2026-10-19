#!/usr/bin/env python3
"""Digest school documents (IEP, 504, neuropsych, past notes) into a
one-page summary for the psychiatrist.

    python3 digest.py samples/*.pdf --out samples/summary.html

PROTOTYPE ONLY. The model call goes through the local `claude -p` CLI on a
consumer account with no BAA. Use synthetic documents, never real patients.

Every fact the model returns must carry a verbatim quote from the page it
cites. Facts whose quote is not found on that page, and scores whose number
is not inside the quote, are moved to an "Unverified" box instead of being
printed as fact.
"""
import argparse
import html
import json
import re
import subprocess
import sys
from pathlib import Path

WARNING = ("PROTOTYPE: no BAA covers this model call. "
           "Synthetic or fully de-identified documents only.")

SCAN_THRESHOLD = 50  # characters per file below which we treat it as a scan

ITEM_SECTIONS = [
    ("documents", "Documents on file"),
    ("key_dates", "Key dates"),
    ("eligibility", "Eligibility"),
    ("diagnoses", "Diagnoses named in the documents"),
    ("scores", "Test scores"),
    ("services", "Services"),
    ("accommodations", "Accommodations"),
    ("concerns", "Teacher and parent concerns"),
]

PROMPT = """You are summarizing school and testing documents for a child and adolescent psychiatrist before a visit.

Return ONLY a JSON object, no prose, no code fences, with exactly these keys:

{
  "student": {"name": str, "grade": str, "school": str},
  "documents":      [ITEM],   // one per document: text = "<type>, dated <date>"
  "key_dates":      [ITEM],   // IEP date, next annual review, triennial, testing dates
  "eligibility":    [ITEM],   // IDEA category or 504 qualifying condition
  "diagnoses":      [ITEM],   // diagnoses as named in the documents, with who made them
  "scores":         [SCORE],
  "services":       [ITEM],   // include minutes and frequency
  "accommodations": [ITEM],
  "concerns":       [ITEM],   // prefix text with the reporter, e.g. "Teacher (ELA): ..."
  "gaps":           [{"text": str, "why": str}],
  "suggested_letter": {"type": str, "why": str}
}

ITEM  = {"text": str, "source": "<file name>", "page": int, "quote": "<exact words copied from that page>"}
SCORE = {"test": str, "measure": str, "score": str, "percentile": str or "", "source": str, "page": int, "quote": str}

Rules:
- "quote" must be copied character for character from the cited page. Keep it short (under 25 words).
  For table rows, quote the row as it appears, e.g. "Working Memory (WMI) 86 18".
- Never compute, round, or infer a number. Only report numbers printed in the documents.
- If documents disagree (e.g. an older 504 and a newer IEP), report both and note the newer one supersedes in "gaps" only if that matters clinically.
- "gaps" are your clinical inferences: missing information a psychiatrist needs (e.g. no teacher rating scale on file),
  or mismatches between test findings and current supports. At most 5 gaps, most important first.
  "text" is a short headline; "why" is ONE sentence. These need no quote, but any number in them must be printed in the documents.
- "suggested_letter": the single most useful letter the psychiatrist could write next (e.g. IEP accommodation support letter,
  504 testing accommodation letter), and why in at most two sentences.

Documents follow. Each page is headed === FILE: <name> | PAGE <n> ===.
"""


def extract_pages(path):
    """Return a list of page texts using pdftotext; pages are split on form feeds."""
    out = subprocess.run(["pdftotext", "-layout", str(path), "-"],
                         capture_output=True, text=True, check=True).stdout
    pages = out.split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    return pages


def norm(s):
    return re.sub(r"\s+", " ", s or "").strip().lower()


def build_prompt(docs, scans):
    parts = [PROMPT]
    for name, pages in docs.items():
        for i, text in enumerate(pages, 1):
            parts.append(f"=== FILE: {name} | PAGE {i} ===\n{text.strip()}\n")
    for name, path in scans.items():
        parts.append(f"=== FILE: {name} is a scanned PDF with no text layer. "
                     f"Read it with the Read tool at {path} and cite pages from it. ===\n")
    return "\n".join(parts)


def call_model(prompt, scans):
    cmd = ["claude", "-p", "--output-format", "text"]
    if scans:
        cmd += ["--allowedTools", "Read"]
    res = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=600)
    if res.returncode != 0:
        sys.exit(f"claude -p failed: {res.stderr.strip()[:500]}")
    raw = res.stdout.strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0:
        sys.exit("model returned no JSON:\n" + raw[:500])
    return json.loads(raw[start:end + 1])


def verify(data, docs, scans):
    """Split every cited item into verified and unverified. Returns the unverified list."""
    unverified = []
    page_text = {(name, i): norm(t) for name, pages in docs.items() for i, t in enumerate(pages, 1)}

    def check(item, numbers=()):
        src, page, quote = item.get("source"), item.get("page"), norm(item.get("quote"))
        if src in scans:
            item["scan"] = True  # no text layer to check against
            return True
        text = page_text.get((src, page))
        if text is None:
            return "cited page does not exist"
        if not quote or quote not in text:
            return "quote not found on cited page"
        for n in numbers:
            if n and not re.search(rf"(?<![\d.]){re.escape(str(n))}(?![\d.])", quote):
                return f"{n} is not in the quoted line"
        return True

    for key, _ in ITEM_SECTIONS:
        kept = []
        for item in data.get(key) or []:
            numbers = (item.get("score"), item.get("percentile")) if key == "scores" else ()
            result = check(item, numbers)
            if result is True:
                kept.append(item)
            else:
                item["section"], item["reason"] = key, result
                unverified.append(item)
        data[key] = kept

    if docs and not scans:  # with a scan there is no full text to check against
        all_text = " ".join(page_text.values())
        free = list(data.get("gaps") or []) + ([data["suggested_letter"]] if data.get("suggested_letter") else [])
        for g in free:
            words = f"{g.get('text', '')} {g.get('why', '')}"
            missing = [n for n in re.findall(r"(?<![\d/.])\d+(?:\.\d+)?(?![\d/])", words)
                       if not re.search(rf"(?<![\d.]){re.escape(n)}(?![\d.])", all_text)]
            if missing:
                g["unchecked_numbers"] = missing
    return unverified


def ordinal(n):
    n = str(n)
    if not n.isdigit():
        return n
    suffix = "th" if 10 <= int(n) % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(int(n) % 10, "th")
    return n + suffix


def item_text(key, item):
    if key == "scores":
        pct = f", {ordinal(item['percentile'])} percentile" if item.get("percentile") else ""
        return f"{item.get('test', '')} {item.get('measure', '')}: {item.get('score', '')}{pct}".strip()
    return item.get("text", "")


def headline(text):
    return text.rstrip(".!?: ")


def number_warning(item):
    nums = item.get("unchecked_numbers")
    return f" [not found in documents: {', '.join(nums)}]" if nums else ""


def cite(item):
    tag = f"{item.get('source')} p.{item.get('page')}"
    return tag + (" (scan, not checked)" if item.get("scan") else "")


CSS = """
body{font:14px/1.45 -apple-system,Helvetica,Arial,sans-serif;max-width:820px;margin:28px auto;color:#1d2433;padding:0 16px}
h1{font-size:20px;margin:0}
.sub{color:#5b6475;margin:2px 0 14px}
.warn{background:#fff4e5;border:1px solid #f0b55a;padding:6px 10px;border-radius:6px;font-size:12px;margin-bottom:14px}
h2{font-size:13px;text-transform:uppercase;letter-spacing:.04em;color:#2c5d63;border-bottom:1px solid #d7dde5;padding-bottom:3px;margin:16px 0 6px}
ul{margin:0;padding-left:18px} li{margin:2px 0}
.src{color:#8a93a3;font-size:11px;margin-left:6px;white-space:nowrap}
table{border-collapse:collapse;width:100%} td,th{border-bottom:1px solid #eef1f5;padding:3px 6px;text-align:left}
th{font-size:12px;color:#5b6475}
.gap li{color:#7a3e00}
.letter{background:#eef6f6;border-radius:6px;padding:8px 10px}
.bad{background:#fdecec;border:1px solid #e3a1a1;border-radius:6px;padding:6px 10px}
.bad .why{color:#a33}
@media print{body{margin:0} .warn{display:none}}
"""


def render_html(data, unverified, files):
    e = html.escape
    s = data.get("student") or {}
    out = [f"<!doctype html><html><head><meta charset='utf-8'><title>School intake: {e(s.get('name', ''))}</title>",
           f"<style>{CSS}</style></head><body>",
           f"<div class='warn'>{e(WARNING)}</div>",
           f"<h1>{e(s.get('name', 'Student'))}</h1>",
           f"<div class='sub'>Grade {e(s.get('grade', '?'))} · {e(s.get('school', ''))} · from {len(files)} document(s)</div>"]

    if data.get("gaps"):
        out.append("<h2>Gaps before the visit</h2><ul class='gap'>")
        out += [f"<li><b>{e(headline(g.get('text', '')))}.</b> {e(g.get('why', ''))}{e(number_warning(g))}</li>" for g in data["gaps"]]
        out.append("</ul>")

    letter = data.get("suggested_letter") or {}
    if letter.get("type"):
        out.append(f"<h2>Suggested letter</h2><div class='letter'><b>{e(headline(letter['type']))}.</b> "
                   f"{e(letter.get('why', ''))}{e(number_warning(letter))}</div>")

    for key, title in ITEM_SECTIONS:
        items = data.get(key) or []
        if not items:
            continue
        out.append(f"<h2>{title}</h2>")
        if key == "scores":
            out.append("<table><tr><th>Test</th><th>Measure</th><th>Score</th><th>%ile</th><th></th></tr>")
            for it in items:
                out.append(f"<tr><td>{e(it.get('test', ''))}</td><td>{e(it.get('measure', ''))}</td>"
                           f"<td><b>{e(str(it.get('score', '')))}</b></td><td>{e(str(it.get('percentile', '')))}</td>"
                           f"<td class='src'>{e(cite(it))}</td></tr>")
            out.append("</table>")
        else:
            out.append("<ul>" + "".join(f"<li>{e(item_text(key, it))}<span class='src'>{e(cite(it))}</span></li>"
                                        for it in items) + "</ul>")

    if unverified:
        out.append("<h2>Unverified, not shown above</h2><div class='bad'><ul>")
        out += [f"<li>{e(item_text(it['section'], it))} <span class='why'>({e(it['reason'])}: {e(cite(it))})</span></li>"
                for it in unverified]
        out.append("</ul></div>")

    out.append("</body></html>")
    return "\n".join(out)


def render_pdf(data, unverified, files, path):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    ss = getSampleStyleSheet()
    body = ParagraphStyle("b", parent=ss["BodyText"], fontSize=9, leading=11.5)
    head = ParagraphStyle("h", parent=ss["Heading4"], fontSize=9.5, textColor=colors.HexColor("#2c5d63"),
                          spaceBefore=6, spaceAfter=2)
    small = "<font size=7 color='#8a93a3'>  {}</font>"
    e = html.escape
    s = data.get("student") or {}
    story = [Paragraph(f"<b>{e(s.get('name', 'Student'))}</b>", ss["Heading2"]),
             Paragraph(f"Grade {e(s.get('grade', '?'))} · {e(s.get('school', ''))} · from {len(files)} document(s)", body),
             Paragraph(f"<font size=7 color='#a35f00'>{e(WARNING)}</font>", body)]

    if data.get("gaps"):
        story.append(Paragraph("GAPS BEFORE THE VISIT", head))
        story += [Paragraph(f"• <b>{e(headline(g.get('text', '')))}.</b> {e(g.get('why', ''))}"
                            f"<font color='#a33'>{e(number_warning(g))}</font>", body) for g in data["gaps"]]
    letter_ = data.get("suggested_letter") or {}
    if letter_.get("type"):
        story.append(Paragraph("SUGGESTED LETTER", head))
        story.append(Paragraph(f"<b>{e(headline(letter_['type']))}.</b> {e(letter_.get('why', ''))}"
                               f"<font color='#a33'>{e(number_warning(letter_))}</font>", body))

    for key, title in ITEM_SECTIONS:
        items = data.get(key) or []
        if not items:
            continue
        story.append(Paragraph(title.upper(), head))
        if key == "scores":
            rows = [["Test", "Measure", "Score", "%ile", "Source"]]
            rows += [[it.get("test", ""), it.get("measure", ""), str(it.get("score", "")),
                      str(it.get("percentile", "")), cite(it)] for it in items]
            t = Table(rows, hAlign="LEFT", colWidths=[70, 170, 40, 35, 150])
            t.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 8), ("TEXTCOLOR", (4, 1), (4, -1), colors.grey),
                                   ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.grey),
                                   ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
            story.append(t)
        else:
            story += [Paragraph("• " + e(item_text(key, it)) + small.format(e(cite(it))), body) for it in items]

    if unverified:
        story.append(Paragraph("UNVERIFIED, NOT SHOWN ABOVE", head))
        story += [Paragraph(f"<font color='#a33'>• {e(item_text(it['section'], it))} ({e(it['reason'])}: {e(cite(it))})</font>", body)
                  for it in unverified]
    story.append(Spacer(1, 4))
    SimpleDocTemplate(str(path), pagesize=letter, topMargin=36, bottomMargin=36,
                      leftMargin=44, rightMargin=44).build(story)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, default=Path("summary.html"))
    ap.add_argument("--from-json", type=Path, help="skip the model; re-verify and render a saved model output")
    args = ap.parse_args()
    print(WARNING, file=sys.stderr)

    docs, scans = {}, {}
    for f in args.files:
        pages = extract_pages(f)
        if sum(len(p.strip()) for p in pages) < SCAN_THRESHOLD:
            scans[f.name] = f.resolve()
        else:
            docs[f.name] = pages

    raw_json = args.out.with_suffix(".model.json")
    if args.from_json:
        data = json.loads(args.from_json.read_text())
    else:
        data = call_model(build_prompt(docs, scans), scans)
        raw_json.write_text(json.dumps(data, indent=2))

    unverified = verify(data, docs, scans)
    args.out.write_text(render_html(data, unverified, args.files))
    render_pdf(data, unverified, args.files, args.out.with_suffix(".pdf"))

    print(f"wrote {args.out} and {args.out.with_suffix('.pdf')}"
          + ("" if args.from_json else f" (model output saved to {raw_json})"))
    if unverified:
        print(f"{len(unverified)} item(s) failed the quote check:")
        for it in unverified:
            print(f"  - {item_text(it['section'], it)}: {it['reason']} ({cite(it)})")


if __name__ == "__main__":
    main()
