#!/usr/bin/env python3
r"""LaTeX → Markdown 转换器（video skill 共用）.

把 video skill 产出的 .tex 转成可在网页渲染的 .md。
- 文档结构：\section → ##，\subsection → ###，\subsubsection → ####
- 高亮框：importantbox/knowledgebox/warningbox → GFM callout
- 图：\includegraphics → 占位符 [图：path — 见 PDF]
- TikZ：\begin{tikzpicture}...\end{tikzpicture} → 跳过
- 代码：lstlisting → 代码块
- 公式：$...$ 和 $$...$$ 保留（remark-math 识别），转换过程中受保护
- 元数据：\notetitle \videochannel 等 → frontmatter
- 链接：\href{url}{text} → [text](url)
- \tableofcontents / \newpage / \titlepage → 删除

用法:
    python3 tex_to_md.py <input.tex> <output.md>

依赖: 无（纯 Python，正则处理）
"""

import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# 数学公式保护：把 $...$ 和 $$...$$ 替换为占位符，转换完再还原
# ---------------------------------------------------------------------------

_MATH_PLACEHOLDER_RE = re.compile(r"@@MATH_(\d+)@@")


def protect_math(tex: str) -> tuple[str, dict[str, str]]:
    """把所有 $$...$$ 和 $...$ 块替换为 @@MATH_N@@ 占位符."""
    store: dict[str, str] = {}

    def save(m: re.Match) -> str:
        key = f"@@MATH_{len(store)}@@"
        store[key] = m.group(0)
        return key

    # 先匹配 $$...$$（贪婪），再匹配 $...$（非贪婪，不含换行）
    # 注意：\$ 是转义美元符号，不应被当作公式起始
    # 先把 \$ 暂存为另一个占位符避免误匹配
    dollar_store: dict[str, str] = {}

    def save_dollar(m: re.Match) -> str:
        key = f"@@DOLLAR_{len(dollar_store)}@@"
        dollar_store[key] = m.group(0)
        return key

    tex = re.sub(r"\\\$", save_dollar, tex)
    # $$...$$ 优先（display math）
    tex = re.sub(r"\$\$.*?\$\$", save, tex, flags=re.DOTALL)
    # $...$（inline math，不跨行）
    tex = re.sub(r"\$[^\$\n]+?\$", save, tex)
    # 还原 \$
    for key, val in dollar_store.items():
        tex = tex.replace(key, val)
    return tex, store


def restore_math(tex: str, store: dict[str, str]) -> str:
    """把 @@MATH_N@@ 占位符还原为原始公式."""

    def restore(m: re.Match) -> str:
        key = m.group(0)
        return store.get(key, key)

    # 循环还原（占位符可能被嵌套保护，虽然概率小）
    prev = None
    while prev != tex:
        prev = tex
        tex = _MATH_PLACEHOLDER_RE.sub(restore, tex)
    return tex


# ---------------------------------------------------------------------------
# 元数据提取
# ---------------------------------------------------------------------------

def extract_metadata(tex: str) -> dict:
    """提取 \\newcommand 定义的元数据."""
    meta = {}
    patterns = {
        "title": r"\\newcommand\{\\notetitle\}\{(.+?)\}",
        "channel": r"\\newcommand\{\\videochannel\}\{(.+?)\}",
        "publish_date": r"\\newcommand\{\\videopublishdate\}\{(.+?)\}",
        "duration": r"\\newcommand\{\\videoduration\}\{(.+?)\}",
        "url": r"\\newcommand\{\\videourl\}\{(.+?)\}",
    }
    for key, pat in patterns.items():
        m = re.search(pat, tex)
        if m:
            val = m.group(1).strip()
            if val and not val.startswith("[在此填写"):
                meta[key] = val
    return meta


# ---------------------------------------------------------------------------
# 结构清理
# ---------------------------------------------------------------------------

def strip_latex_wrappers(tex: str) -> str:
    """删除 documentclass/preamble/titlepage/toc 等，只保留正文."""
    tex = re.sub(r"\\documentclass.*?\\begin\{document\}", "", tex, flags=re.DOTALL)
    tex = re.sub(r"\\end\{document\}.*$", "", tex, flags=re.DOTALL)
    tex = re.sub(r"\\begin\{titlepage\}.*?\\end\{titlepage\}", "", tex, flags=re.DOTALL)
    tex = re.sub(r"\\(tableofcontents|newpage|clearpage)\b", "", tex)
    # 删除 \newcommand 定义行
    tex = re.sub(r"\\newcommand\{\\[^}]+\}\{[^}]*\}", "", tex)
    # 删除 \usepackage{...} 等残留 preamble 命令
    tex = re.sub(r"\\(usepackage|input|include)\{[^}]*\}", "", tex)
    return tex


# ---------------------------------------------------------------------------
# 章节转换
# ---------------------------------------------------------------------------

def convert_sections(tex: str) -> str:
    """转换章节命令."""
    tex = re.sub(r"\\section\*?\{([^}]*)\}", r"## \1", tex)
    tex = re.sub(r"\\subsection\*?\{([^}]*)\}", r"### \1", tex)
    tex = re.sub(r"\\subsubsection\*?\{([^}]*)\}", r"#### \1", tex)
    tex = re.sub(r"\\paragraph\*?\{([^}]*)\}", r"##### \1", tex)
    return tex


# ---------------------------------------------------------------------------
# tcolorbox 转换
# ---------------------------------------------------------------------------

_TYPE_MAP = {
    "importantbox": "IMPORTANT",
    "knowledgebox": "NOTE",
    "warningbox": "WARNING",
}


def _make_callout(box_type: str, title: str, content: str) -> str:
    callout_type = _TYPE_MAP.get(box_type, "NOTE")
    title_str = f"**{title}**" if title else ""
    lines = content.strip().split("\n")
    prefixed = "\n".join(f"> {line}" if line.strip() else ">" for line in lines)
    header = f"> [!{callout_type}]"
    if title_str:
        header += f" {title_str}"
    return f"{header}\n{prefixed}\n"


def convert_tcolorbox(tex: str) -> str:
    """转换 importantbox/knowledgebox/warningbox 为 GFM callout."""
    for box in ("importantbox", "knowledgebox", "warningbox"):
        callout_type = box  # 闭包绑定

        def replacer(match, _box=callout_type):
            # group(1) = title（可选），group(2) = content
            title = match.group(1) or ""
            content = match.group(2) or ""
            return _make_callout(_box, title, content)

        pattern = rf"\\begin\{{{box}\}}(?:\{{([^}}]*)\}})?(.*?)\\end\{{{box}\}}"
        tex = re.sub(pattern, replacer, tex, flags=re.DOTALL)
    return tex


# ---------------------------------------------------------------------------
# 图片 / TikZ / 代码块
# ---------------------------------------------------------------------------

def convert_includegraphics(tex: str) -> str:
    """\\includegraphics[...]{path} → 占位符."""
    def replacer(match):
        path = match.group(1)
        return f"[图：{path} — 见 PDF]"

    tex = re.sub(
        r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}",
        replacer,
        tex,
    )
    return tex


def strip_tikz(tex: str) -> str:
    """跳过 TikZ 块（含包裹它的 figure 环境）."""
    def figure_replacer(match):
        content = match.group(1)
        if "tikzpicture" in content:
            return "[图：TikZ 可视化 — 见 PDF]"
        return match.group(0)

    tex = re.sub(
        r"\\begin\{figure\}(?:\[[^\]]*\])?(.*?)\\end\{figure\}",
        figure_replacer,
        tex,
        flags=re.DOTALL,
    )
    tex = re.sub(
        r"\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}",
        "[图：TikZ 可视化 — 见 PDF]",
        tex,
        flags=re.DOTALL,
    )
    return tex


def convert_lstlisting(tex: str) -> str:
    """\\begin{lstlisting}[language=Python]...\\end{lstlisting} → 代码块."""
    _lang_map = {"python": "python", "c": "c", "c++": "cpp", "java": "java",
                 "javascript": "javascript", "bash": "bash", "shell": "bash"}

    def replacer(match):
        opts = match.group(1) or ""
        content = match.group(2)
        lang_match = re.search(r"language=(\w+)", opts)
        lang = lang_match.group(1).lower() if lang_match else ""
        lang = _lang_map.get(lang, lang)
        return f"```{lang}\n{content.strip()}\n```"

    tex = re.sub(
        r"\\begin\{lstlisting\}(?:\[([^\]]*)\])?(.*?)\\end\{lstlisting\}",
        replacer,
        tex,
        flags=re.DOTALL,
    )
    return tex


# ---------------------------------------------------------------------------
# 链接 / 脚注 / figure 环境
# ---------------------------------------------------------------------------

def convert_href(tex: str) -> str:
    """\\href{url}{text} → [text](url)."""
    tex = re.sub(r"\\href\{([^}]+)\}\{([^}]+)\}", r"[\2](\1)", tex)
    return tex


def convert_footnote(tex: str) -> str:
    """\\footnotetext{...} → 单独行引用."""
    def replacer(match):
        content = match.group(1).strip()
        return f"\n*{content}*\n"

    tex = re.sub(r"\\footnotetext\{([^}]+)\}", replacer, tex)
    tex = re.sub(r"\\footnotemark\b", "", tex)
    return tex


def strip_remaining_figure_env(tex: str) -> str:
    """处理剩余的 figure 环境（不含 tikz 的）."""
    def replacer(match):
        content = match.group(1)
        content = re.sub(r"\\centering\b", "", content)
        content = re.sub(r"\\caption\{([^}]*)\}", r"*\1*", content)
        content = re.sub(r"\\label\{[^}]*\}", "", content)
        return content.strip()

    tex = re.sub(
        r"\\begin\{figure\}(?:\[[^\]]*\])?(.*?)\\end\{figure\}",
        replacer,
        tex,
        flags=re.DOTALL,
    )
    return tex


# ---------------------------------------------------------------------------
# 剩余 LaTeX 命令清理（注意：此时公式已被保护，不会被误伤）
# ---------------------------------------------------------------------------

def strip_latex_commands(tex: str) -> str:
    """清理剩余的 LaTeX 命令."""
    tex = re.sub(r"\\textbf\{([^}]*)\}", r"**\1**", tex)
    tex = re.sub(r"\\textit\{([^}]*)\}", r"*\1*", tex)
    tex = re.sub(r"\\emph\{([^}]*)\}", r"*\1*", tex)
    tex = re.sub(r"\\texttt\{([^}]*)\}", r"`\1`", tex)
    tex = re.sub(r"\\url\{([^}]+)\}", r"<\1>", tex)
    tex = re.sub(r"\\nolinkurl\{([^}]+)\}", r"\1", tex)
    tex = re.sub(r"\\par\b", "\n\n", tex)
    tex = re.sub(r"\\(vspace|hspace)\{[^}]*\}", "", tex)
    tex = re.sub(r"\\(vfill|hfill|small|large|Large|normalsize|tiny|footnotesize)\b", "", tex)
    tex = re.sub(r"\\label\{[^}]*\}", "", tex)
    tex = re.sub(r"\\ref\{([^}]+)\}", r"[\1]", tex)
    tex = re.sub(r"\\cite\{([^}]+)\}", r"[cite]", tex)
    tex = re.sub(r"\\\\", "\n", tex)
    # 剩余的未知命令 \xxx{...} → 内容
    tex = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", tex)
    # 剩余的 \xxx（无参数）→ 删除
    tex = re.sub(r"\\[a-zA-Z]+\b", "", tex)
    return tex


def cleanup(tex: str) -> str:
    """清理多余空行和空白."""
    tex = re.sub(r"\n{3,}", "\n\n", tex)
    lines = [line.rstrip() for line in tex.split("\n")]
    tex = "\n".join(lines)
    return tex.strip()


# ---------------------------------------------------------------------------
# Frontmatter
# ---------------------------------------------------------------------------

def build_frontmatter(meta: dict, tex_path: Path) -> str:
    """构建 frontmatter."""
    title = meta.get("title", "")
    if title.startswith("课程笔记："):
        title = title.replace("课程笔记：", "").strip()

    fm = ["---"]
    fm.append(f"title: {title}")
    fm.append("topic: video")
    fm.append("tags: [video]")
    if meta.get("channel"):
        fm.append(f"summary: 视频笔记 — {meta['channel']}")
    else:
        fm.append("summary: 视频笔记")
    if meta.get("publish_date"):
        fm.append(f"created: {meta['publish_date']}")
        fm.append(f"updated: {meta['publish_date']}")
    else:
        import datetime
        today = datetime.date.today().isoformat()
        fm.append(f"created: {today}")
        fm.append(f"updated: {today}")
    if meta.get("url"):
        fm.append(f"video_url: {meta['url']}")
    if meta.get("channel"):
        fm.append(f"video_channel: {meta['channel']}")
    if meta.get("duration"):
        fm.append(f"video_duration: {meta['duration']}")
    pdf_name = tex_path.stem + ".pdf"
    fm.append(f"source: {pdf_name}")
    fm.append("---")
    return "\n".join(fm)


# ---------------------------------------------------------------------------
# 主转换
# ---------------------------------------------------------------------------

def convert(tex_path: Path, md_path: Path) -> None:
    """主转换函数."""
    tex = tex_path.read_text(encoding="utf-8")

    # 1. 提取元数据（在保护公式前，因为 \newcommand 可能含 $）
    meta = extract_metadata(tex)

    # 2. 保护数学公式（关键：后续所有转换都不会动 $...$ 内容）
    body, math_store = protect_math(tex)

    # 3. 删除 preamble/titlepage/toc/newcommand 定义
    body = strip_latex_wrappers(body)

    # 4. 转换各元素（顺序重要）
    body = convert_tcolorbox(body)
    body = strip_tikz(body)
    body = convert_lstlisting(body)
    body = convert_includegraphics(body)
    body = strip_remaining_figure_env(body)
    body = convert_sections(body)
    body = convert_href(body)
    body = convert_footnote(body)
    body = strip_latex_commands(body)
    body = cleanup(body)

    # 5. 还原数学公式
    body = restore_math(body, math_store)
    body = cleanup(body)

    # 6. 组装 frontmatter + body
    fm = build_frontmatter(meta, tex_path)
    title_for_h1 = meta.get("title", "").replace("课程笔记：", "").strip() or tex_path.stem
    md = f"{fm}\n\n# {title_for_h1}\n\n{body}\n"

    md_path.write_text(md, encoding="utf-8")
    print(f"OK: {tex_path} → {md_path} ({len(md)} chars)")


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 tex_to_md.py <input.tex> <output.md>", file=sys.stderr)
        sys.exit(1)
    tex_path = Path(sys.argv[1])
    md_path = Path(sys.argv[2])
    if not tex_path.exists():
        print(f"ERROR: {tex_path} not found", file=sys.stderr)
        sys.exit(1)
    convert(tex_path, md_path)


if __name__ == "__main__":
    main()
