#!/usr/bin/env python3
"""Frame quality assessment via SiliconFlow DeepSeek-OCR API.

Usage:
    python3 frame_assess.py <image_path>              # assess a single frame
    python3 frame_assess.py --batch <glob_pattern>    # assess multiple, rank by score
    python3 frame_assess.py --batch <pattern> --top 3 # keep top N only

API key: write it into ~/.config/bilibili-render-pdf/siliconflow_key
(one line, plain text).  Falls back to ./.config/siliconflow_key.
"""

import argparse, base64, json, os, re, sys, glob as glob_mod
from pathlib import Path

BASE_URL = "https://api.siliconflow.cn/v1"
MODEL   = "deepseek-ai/DeepSeek-OCR"

def load_api_key():
    for p in [
        Path.home() / ".config" / "bilibili-render-pdf" / "siliconflow_key",
        Path(".config") / "siliconflow_key",
    ]:
        if p.exists():
            return p.read_text().strip()
    print("ERROR: siliconflow_key not found.", file=sys.stderr)
    sys.exit(1)

def image_to_data_uri(path: str) -> str:
    ext = Path(path).suffix.lower().lstrip(".")
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp"}.get(ext, "jpeg")
    b64 = base64.b64encode(Path(path).read_bytes()).decode()
    return f"data:image/{mime};base64,{b64}"

def clean_ocr_text(raw: str) -> str:
    raw = re.sub(r'<\|box_start\|>\d+<\|box_end\|>', '', raw)
    raw = re.sub(r'<\|ref_start\|>\w+<\|ref_end\|>', '', raw)
    raw = re.sub(r'<\|md_start\|>', '', raw)
    raw = re.sub(r'<\|quad_start\|>.*?<\|quad_end\|>', '', raw, flags=re.DOTALL)
    raw = re.sub(r'\n{3,}', '\n\n', raw)
    return raw.strip()

def classify_frame(ocr_text: str, char_count: int) -> tuple:
    """Return (type, info_score)."""
    if char_count < 5:
        return "talking_head", 1

    lines = [l for l in ocr_text.split('\n') if l.strip()]
    # code detection: significant indentation + keywords, but not markdown headings
    code_lines = sum(1 for l in lines if (l.startswith(('    ', '\t')) and len(l) > 4)
                     or any(l.startswith(kw + ' ') for kw in ['def ', 'class ', 'import ', 'from ']))
    if code_lines >= 2:
        return "code", min(5, max(3, char_count // 60))

    if char_count < 30:
        return "other", 2
    elif char_count < 100:
        return "slide", 3
    elif char_count < 300:
        return "slide", 4
    else:
        return "slide", 5

def assess_frame(path: str, client) -> dict:
    data_uri = image_to_data_uri(path)

    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "你是一个 OCR 工具。只输出从图片中识别到的所有文字，不做任何解释。输出纯文本。"},
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": data_uri}},
                {"type": "text", "text": "提取所有文字。"},
            ]},
        ],
        temperature=0.0,
        max_tokens=1024,
    )
    raw_text = resp.choices[0].message.content
    ocr_text = clean_ocr_text(raw_text)
    char_count = len(re.sub(r'[\s\n]', '', ocr_text))

    ftype, info_score = classify_frame(ocr_text, char_count)
    has_text = char_count > 5
    suitable = info_score >= 3 and has_text

    return {
        "type": ftype,
        "info_score": info_score,
        "has_text": has_text,
        "ocr_text": ocr_text[:400],
        "char_count": char_count,
        "suitable_for_notes": suitable,
        "reason": f"OCR 提取到 {char_count} 个有效字符" + ("，适合放入笔记" if suitable else "，文字量不足"),
        "_file": path,
    }

def main():
    parser = argparse.ArgumentParser(description="Frame quality assessment via OCR")
    parser.add_argument("path", nargs="?", help="Single image path")
    parser.add_argument("--batch", help="Glob pattern for batch assessment")
    parser.add_argument("--top", type=int, default=0, help="Keep only top N frames")
    args = parser.parse_args()

    from openai import OpenAI
    api_key = load_api_key()
    client = OpenAI(api_key=api_key, base_url=BASE_URL)

    if args.batch:
        files = sorted(glob_mod.glob(args.batch))
        if not files:
            print(f"No files matched: {args.batch}", file=sys.stderr)
            sys.exit(1)
        print(f"Assessing {len(files)} frames via {MODEL}...", file=sys.stderr)
        results = []
        for i, f in enumerate(files):
            r = assess_frame(f, client)
            results.append(r)
            score = r["info_score"]
            stype = r["type"]
            chars = r["char_count"]
            suitable = "YES" if r["suitable_for_notes"] else "no"
            print(f"  [{i+1}/{len(files)}] [{score}/5] [{suitable}] {chars}c {stype:14s} {Path(f).name}", file=sys.stderr)
        results.sort(key=lambda r: r.get("info_score", 0), reverse=True)
        if args.top > 0:
            results = results[:args.top]
        print(json.dumps(results, ensure_ascii=False, indent=2))
    elif args.path:
        r = assess_frame(args.path, client)
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
