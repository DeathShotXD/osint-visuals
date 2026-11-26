#!/usr/bin/env python3
"""Turn a plain-text script into a scrolling story: a map that flies between places, pictures that change, a
before/after divider that moves as you scroll, with the text cards passing over them. Standard library only.

  story.py story.md                      -> story.html (one self-contained page; local images are embedded)
  story.py story.md --svelte out/        -> also a Svelte 5 + Vite project for a newsroom's own build

The script format (see examples/scroll-story/demo.md):

  ---
  title: A tanker goes dark
  dek: One line under the title
  byline: OSINT JOURNO
  theme: dark            (or light)
  sources: Positions: ...; Imagery: ...
  ---

  [map 24.62,58.30 zoom=7 marker="Meeting point"]
  Text for this step. **Bold**, *italic* and [links](https://example.org) work.

  [map 24.62,58.30 zoom=11 pitch=50 bearing=-20]
  ...
  [image photos/frame.jpg credit="Video: ..." alt="What the picture shows"]
  ...
  [compare before.jpg after.jpg labels="29 Jul|18 Aug" credit="Imagery: ..."]
  ...
  [text]
  A text-only step: the picture behind dims.
"""
import argparse
import base64
import html
import json
import os
import re
import shlex
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


def page_json(obj):
    """JSON for a <script> block. '<' is escaped so an input value can never close the tag."""
    return (json.dumps(obj, separators=(",", ":"))
            .replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e"))

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "..", "assets", "story.html")
SVELTE = os.path.join(HERE, "..", "assets", "svelte")
MIME = {".png": "image/png", ".webp": "image/webp", ".gif": "image/gif", ".svg": "image/svg+xml", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}


def inline(md):
    """Markdown-lite for step text: escape, then **bold**, *italic*, [text](url). Paragraphs on blank lines."""
    out = []
    for para in re.split(r"\n\s*\n", md.strip()):
        t = html.escape(" ".join(para.split()), quote=False)
        t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
        t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", t)
        t = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", lambda m: f'<a href="{html.escape(m.group(2))}" target="_blank" rel="noopener">{m.group(1)}</a>', t)
        if t: out.append(f"<p>{t}</p>")
    return "".join(out)


def parse(text, base):
    meta, body = {}, text
    m = re.match(r"\s*---\s*\n(.*?)\n---\s*\n(.*)", text, re.S)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1); meta[k.strip().lower()] = v.strip()
        body = m.group(2)
    steps, cur = [], None
    for line in body.splitlines():
        tag = re.match(r"^\s*\[(map|image|compare|text)\b(.*)\]\s*$", line)
        if tag:
            if cur: steps.append(cur)
            kind, rest = tag.group(1), tag.group(2).strip()
            parts = shlex.split(rest) if rest else []
            args = [p for p in parts if "=" not in p]; opts = dict(p.split("=", 1) for p in parts if "=" in p)
            cur = {"kind": kind, "args": args, "opts": opts, "text": ""}
        elif cur is not None:
            cur["text"] += line + "\n"
        elif line.strip():
            sys.exit(f"text before the first [map]/[image]/[compare]/[text] step: {line.strip()[:60]!r}")
    if cur: steps.append(cur)
    if not steps: sys.exit("no steps found: start each step with a line like [map LAT,LON zoom=8] or [image file.jpg]")
    out, credits = [], []
    for i, s in enumerate(steps):
        o, st = s["opts"], {"kind": s["kind"], "html": inline(s["text"])}
        if s["kind"] == "map":
            try: la, lo = map(float, s["args"][0].split(","))
            except (IndexError, ValueError): sys.exit(f"step {i + 1}: [map LAT,LON ...] needs coordinates")
            st.update({"center": [lo, la], "zoom": float(o.get("zoom", 8)), "pitch": float(o.get("pitch", 0)), "bearing": float(o.get("bearing", 0))})
            if "marker" in o: st["marker"] = {"lnglat": [lo, la], "label": o["marker"]}
            if "markers" in o:   # markers="lat,lon,label;lat,lon,label"
                st["markers"] = [{"lnglat": [float(p.split(",")[1]), float(p.split(",")[0])], "label": p.split(",", 2)[2]} for p in o["markers"].split(";") if p.count(",") >= 2]
        elif s["kind"] == "image":
            if not s["args"]: sys.exit(f"step {i + 1}: [image FILE] needs a file or URL")
            st.update({"src": s["args"][0], "alt": o.get("alt", ""), "credit": o.get("credit", ""), "fit": o.get("fit", "contain")})
            if not o.get("credit"): print(f"  note: step {i + 1} image has no credit=; add who made or owns it")
            if not o.get("alt"): print(f"  note: step {i + 1} image has no alt=; describe it for screen readers")
        elif s["kind"] == "compare":
            if len(s["args"]) < 2: sys.exit(f"step {i + 1}: [compare BEFORE AFTER] needs two images")
            labels = (o.get("labels", "Before|After").split("|") + ["After"])[:2]
            st.update({"before": s["args"][0], "after": s["args"][1], "labels": labels, "credit": o.get("credit", "")})
        if st.get("credit"): credits.append(st["credit"])
        out.append(st)
    return meta, out, credits


def embed(src, base):
    if re.match(r"^(https?:|data:)", src): return src
    path = src if os.path.isabs(src) else os.path.join(base, src)
    if not os.path.exists(path): sys.exit(f"image not found: {src}")
    return f"data:{MIME.get(os.path.splitext(path)[1].lower(), 'image/jpeg')};base64," + base64.b64encode(Path(path).read_bytes()).decode()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("script"); ap.add_argument("--out", default=None)
    ap.add_argument("--svelte", metavar="DIR", help="also write a Svelte 5 + Vite project here (images copied, not embedded)")
    a = ap.parse_args(argv)
    base = os.path.dirname(os.path.abspath(a.script))
    meta, steps, credits = parse(Path(a.script).read_text(encoding="utf-8"), base)
    uses_map = any(s["kind"] == "map" for s in steps)
    data = {"title": meta.get("title", "Untitled story"), "dek": meta.get("dek", ""), "byline": meta.get("byline", ""), "theme": meta.get("theme", "dark"),
            "sources": meta.get("sources", ""), "credits": credits, "map": uses_map, "steps": steps,
            "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
    page_data = json.loads(json.dumps(data))
    for s in page_data["steps"]:
        for k in ("src", "before", "after"):
            if k in s: s[k] = embed(s[k], base)
    page = Path(TEMPLATE).read_text(encoding="utf-8")
    page = page.replace("/*__DATA__*/null", page_json(page_data)).replace("__TITLE__", html.escape(data["title"]))
    dest = a.out or os.path.splitext(a.script)[0] + ".html"
    Path(dest).write_text(page, encoding="utf-8")
    counts = {k: sum(1 for s in steps if s["kind"] == k) for k in ("map", "image", "compare", "text")}
    print(f"wrote {dest} ({os.path.getsize(dest) // 1024} KB): " + ", ".join(f"{v} {k}" for k, v in counts.items() if v))
    if a.svelte:
        write_svelte(a.svelte, data, base)
    return 0


def write_svelte(dest, data, base):
    """Copy the Svelte project template, put the story in src/story.json and its images in public/media/."""
    if os.path.exists(os.path.join(dest, "package.json")) and not os.path.exists(os.path.join(dest, "src", "story.json")):
        sys.exit(f"{dest} already holds another project; pick an empty folder")
    shutil.copytree(SVELTE, dest, dirs_exist_ok=True)
    media = os.path.join(dest, "public", "media"); os.makedirs(media, exist_ok=True)
    story = json.loads(json.dumps(data))
    for s in story["steps"]:
        for k in ("src", "before", "after"):
            if k in s and not re.match(r"^(https?:|data:)", s[k]):
                src = s[k] if os.path.isabs(s[k]) else os.path.join(base, s[k])
                name = os.path.basename(src); shutil.copy(src, os.path.join(media, name)); s[k] = "media/" + name
    json.dump(story, open(os.path.join(dest, "src", "story.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"wrote a Svelte project in {dest}: cd {dest} && npm install && npm run dev   (npm run build for a static site)")


if __name__ == "__main__":
    sys.exit(main())
