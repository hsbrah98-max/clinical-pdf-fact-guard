#!/usr/bin/env python3
"""Bake the digest output and the teacher form into one deployable file.

    python3 build_app.py                      # uses samples/summary.model.json
    python3 build_app.py --packet other.json --out other.html

Run digest.py first. The output, snowpine-schools.html, has no other dependencies.
"""
import argparse
import json
from pathlib import Path

HERE = Path(__file__).parent


def script_safe(obj):
    """JSON that can sit inside a <script> tag: no '<' can close it early."""
    return json.dumps(obj).replace("<", "\\u003c")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--packet", type=Path, default=HERE / "samples" / "summary.model.json")
    ap.add_argument("--out", type=Path, default=HERE / "snowpine-schools.html")
    args = ap.parse_args()

    html = (HERE / "app_template.html").read_text()
    packet = json.loads(args.packet.read_text()) if args.packet.exists() else None
    teacher = (HERE / "teacher-vanderbilt.html").read_text()

    for marker, value in [("/*__PACKET__*/null", script_safe(packet)),
                          ('"__TEACHER_FORM__"', script_safe(teacher))]:
        assert html.count(marker) == 1, marker
        html = html.replace(marker, value)

    args.out.write_text(html)
    print(f"wrote {args.out.name} ({len(html) // 1024} KB)"
          + ("" if packet else " WITHOUT a records summary: run digest.py first"))


if __name__ == "__main__":
    main()
