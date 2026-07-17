#!/usr/bin/env python3
r"""LaTeX → Markdown 转换器（video skill 共用）.

把 video skill 产出的 .tex 转成可在网页渲染的 .md。
- 文档结构：\section → ##，\subsection → ###，\subsubsection → ####
- 列表：itemize → -，enumerate → 1.
- 高亮框：importantbox/knowledgebox/warningbox → blockquote（带 [重要]/[知识]/[注意] 标签）
- 图：\includegraphics → 占位符 [图：path — 见 PDF]
- TikZ：\begin{tikzpicture}...\end{tikzpicture} → 跳过
- 代码：lstlisting → 代码块
- 公式：$...$ 和 $$...$$ 保留（remark-math 识别），转换过程中受保护
- 符号：\rightarrow → → 等常见 LaTeX 符号转 Unicode
- 元数据：\notetitle \videochannel 等 → frontmatter
- 链接：\href{url}{text} → [text](url)
- \tableofcontents / \newpage / \titlepage / 注释行 → 删除

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

    # \$ 是转义美元符号，不应被当作公式起始，先暂存
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
        return store.get(m.group(0), m.group(0))

    prev = None
    while prev != tex:
        prev = tex
        tex = _MATH_PLACEHOLDER_RE.sub(restore, tex)
    return tex


# ---------------------------------------------------------------------------
# 元数据提取
# ---------------------------------------------------------------------------

def extract_metadata(tex: str) -> dict:
    """提取 \\newcommand 定义的元数据.

    日期格式自动归一化为 ISO 8601（YYYY 或 YYYY-MM 或 YYYY-MM-DD），
    避免 Quartz build 时报 "invalid date" warning。
    支持的输入格式：2025年7月 / 2025年07月 / 2025-07 / 2025-07-01 / 2025/07 等。
    """
    def normalize_date(s: str) -> str:
        s = s.strip()
        # 中文日期：2025年7月 / 2025年07月15日
        m = re.match(r"(\d{4})年(\d{1,2})月(?:(\d{1,2})日)?", s)
        if m:
            y, mo, d = m.group(1), int(m.group(2)), m.group(3)
            out = f"{y}-{mo:02d}"
            if d:
                out += f"-{int(d):02d}"
            return out
        # 斜杠日期：2025/07/01
        m = re.match(r"(\d{4})/(\d{1,2})(?:/(\d{1,2}))?", s)
        if m:
            y, mo, d = m.group(1), int(m.group(2)), m.group(3)
            out = f"{y}-{mo:02d}"
            if d:
                out += f"-{int(d):02d}"
            return out
        return s

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
                if key == "publish_date":
                    val = normalize_date(val)
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


def strip_comments(tex: str) -> str:
    """删除 LaTeX 注释：整行注释 + 行内注释（保护 \\% 转义）.

    行内注释仅在 % 前是空白/行首时才删除，避免误删未转义的字面 %
    （如 "准确率 50%" 这种用户错误写法）。
    """
    lines = tex.split("\n")
    result = []
    for line in lines:
        stripped = line.lstrip()
        # 跳过纯注释行（% 开头，但不是 \%）
        if stripped.startswith("%") and not stripped.startswith("\\%"):
            continue
        # 删除行内注释：% 前必须是空白或行首才当注释
        # 用正则：匹配 (空白或行首)% 之后的所有内容
        line = re.sub(r"(^|\s)%.*$", r"\1", line)
        result.append(line)
    return "\n".join(result)


# ---------------------------------------------------------------------------
# 列表转换（必须在 strip_latex_commands 之前）
# ---------------------------------------------------------------------------

def convert_lists(tex: str) -> str:
    """itemize → 无序列表，enumerate → 有序列表.

    处理嵌套：先递归处理最内层（无子 itemize/enumerate 的），转换并按 2 空格缩进；
    再逐层向外。外层 item 看到内层已转换的 "- ..." 行时，会在行首加 2 空格缩进，
    保留内层已有的缩进（不 lstrip），这样 3 层及以上嵌套也能正确累积缩进。
    """
    def split_items(content: str) -> list[str]:
        items = re.split(r"\\item\b", content)
        return [item.strip() for item in items if item.strip()]

    def itemize_replacer(match):
        content = match.group(1)
        items = split_items(content)
        out_lines = []
        for item in items:
            item_lines = item.split("\n")
            # 第一行作为 item 主体
            first = item_lines[0].strip()
            out_lines.append(f"- {first}")
            # 后续行（已转换的嵌套 "- ..."）保留原缩进 + 叠加 2 空格
            for ln in item_lines[1:]:
                if ln.strip():
                    out_lines.append("  " + ln)
        return "\n" + "\n".join(out_lines) + "\n"

    def enumerate_replacer(match):
        content = match.group(1)
        items = split_items(content)
        out_lines = []
        for i, item in enumerate(items):
            item_lines = item.split("\n")
            first = item_lines[0].strip()
            out_lines.append(f"{i+1}. {first}")
            for ln in item_lines[1:]:
                if ln.strip():
                    out_lines.append("  " + ln)
        return "\n" + "\n".join(out_lines) + "\n"

    # 只处理最内层（无嵌套子列表的 itemize/enumerate），循环上限防死循环
    for _ in range(10):
        new_tex = re.sub(
            r"\\begin\{itemize\}((?:(?!\\begin\{itemize\}|\\begin\{enumerate\}).)*?)\\end\{itemize\}",
            itemize_replacer, tex, flags=re.DOTALL,
        )
        new_tex = re.sub(
            r"\\begin\{enumerate\}((?:(?!\\begin\{itemize\}|\\begin\{enumerate\}).)*?)\\end\{enumerate\}",
            enumerate_replacer, new_tex, flags=re.DOTALL,
        )
        if new_tex == tex:
            break
        tex = new_tex
    return tex


def convert_quote(tex: str) -> str:
    """转换 quote/quotation/verse 环境为 markdown blockquote.

    必须在 strip_latex_commands 之前调用，否则 \\begin{quote} 会被
    兜底规则 \\xxx{arg} → arg 转成字面 "quote" 字符串。
    """
    def quote_replacer(match):
        content = match.group(1).strip()
        lines = content.split("\n")
        return "\n" + "\n".join(f"> {ln}" if ln.strip() else ">" for ln in lines) + "\n"

    for env in ("quote", "quotation", "verse"):
        tex = re.sub(
            rf"\\begin\{{{env}\}}(.*?)\\end\{{{env}\}}",
            quote_replacer, tex, flags=re.DOTALL,
        )
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
# tcolorbox 转换 → 普通 blockquote（不依赖 GFM callout 语法）
# ---------------------------------------------------------------------------

_TYPE_LABEL = {
    "importantbox": "重要",
    "knowledgebox": "知识",
    "warningbox": "注意",
}


def _make_callout(box_type: str, title: str, content: str) -> str:
    label = _TYPE_LABEL.get(box_type, "提示")
    header = f"**[{label}]**"
    if title:
        header += f" **{title}**"
    lines = content.strip().split("\n")
    prefixed = "\n".join(f"> {line}" if line.strip() else ">" for line in lines)
    return f"> {header}\n{prefixed}\n"


def convert_tcolorbox(tex: str) -> str:
    """转换 importantbox/knowledgebox/warningbox 为 blockquote."""
    for box in ("importantbox", "knowledgebox", "warningbox"):
        callout_type = box

        def replacer(match, _box=callout_type):
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
# LaTeX 符号转 Unicode（必须在 strip_latex_commands 之前，否则命令会被删）
# ---------------------------------------------------------------------------

_LATEX_SYMBOLS = {
    r"\rightarrow": "→",
    r"\leftarrow": "←",
    r"\Rightarrow": "⇒",
    r"\Leftarrow": "⇐",
    r"\to": "→",
    r"\gets": "←",
    r"\leftrightarrow": "↔",
    r"\Leftrightarrow": "⇔",
    r"\leq": "≤",
    r"\le": "≤",
    r"\geq": "≥",
    r"\ge": "≥",
    r"\neq": "≠",
    r"\ne": "≠",
    r"\approx": "≈",
    r"\equiv": "≡",
    r"\sim": "∼",
    r"\infty": "∞",
    r"\times": "×",
    r"\div": "÷",
    r"\pm": "±",
    r"\mp": "∓",
    r"\cdot": "·",
    r"\cdots": "⋯",
    r"\ldots": "…",
    r"\dots": "…",
    r"\vdots": "⋮",
    r"\ddots": "⋱",
    r"\alpha": "α",
    r"\beta": "β",
    r"\gamma": "γ",
    r"\delta": "δ",
    r"\epsilon": "ε",
    r"\varepsilon": "ε",
    r"\zeta": "ζ",
    r"\eta": "η",
    r"\theta": "θ",
    r"\vartheta": "ϑ",
    r"\iota": "ι",
    r"\kappa": "κ",
    r"\lambda": "λ",
    r"\mu": "μ",
    r"\nu": "ν",
    r"\xi": "ξ",
    r"\pi": "π",
    r"\varpi": "ϖ",
    r"\rho": "ρ",
    r"\varrho": "ϱ",
    r"\sigma": "σ",
    r"\varsigma": "ς",
    r"\tau": "τ",
    r"\upsilon": "υ",
    r"\phi": "φ",
    r"\varphi": "φ",
    r"\chi": "χ",
    r"\psi": "ψ",
    r"\omega": "ω",
    r"\Gamma": "Γ",
    r"\Delta": "Δ",
    r"\Theta": "Θ",
    r"\Lambda": "Λ",
    r"\Xi": "Ξ",
    r"\Pi": "Π",
    r"\Sigma": "Σ",
    r"\Phi": "Φ",
    r"\Psi": "Ψ",
    r"\Omega": "Ω",
    r"\forall": "∀",
    r"\exists": "∃",
    r"\nexists": "∄",
    r"\in": "∈",
    r"\notin": "∉",
    r"\subset": "⊂",
    r"\subseteq": "⊆",
    r"\supset": "⊃",
    r"\supseteq": "⊇",
    r"\cup": "∪",
    r"\cap": "∩",
    r"\emptyset": "∅",
    r"\nabla": "∇",
    r"\partial": "∂",
    r"\sum": "∑",
    r"\prod": "∏",
    r"\int": "∫",
    r"\oint": "∮",
    r"\sqrt": "√",
    r"\circ": "∘",
    r"\star": "⋆",
    r"\dagger": "†",
    r"\ddagger": "‡",
    r"\bullet": "•",
    r"\ldotp": "·",
    r"\colon": ":",
    r"\degree": "°",
    r"\textdegree": "°",
    r"\checkmark": "✓",
    r"\heartsuit": "♥",
    r"\diamondsuit": "♦",
    r"\clubsuit": "♣",
    r"\spadesuit": "♠",
    r"\#": "#",
    r"\&": "&",
    r"\%": "%",
    r"\_": "_",
    r"\{": "{",
    r"\}": "}",
}
# 注意：\$ 不在此处转换。protect_math 已把 \$ 保护起来，
# 最终保留为 \$（KaTeX 尊重 \$ 为字面美元符号），避免被误判为公式定界符。


def convert_symbols(tex: str) -> str:
    """把常见 LaTeX 符号命令转成 Unicode.

    按 key 长度降序处理 + 正则负向先行断言 `(?![a-zA-Z])`，
    避免短前缀破坏长命令（如 `\\in` 误伤 `\\int`、`\\to` 误伤 `\\top`）。

    例外：转义符（`\\# \\& \\% \\_ \\{ \\}`）后面可能跟字母
    （如 `\\#tag`），不能用 `(?![a-zA-Z])`，单独处理。
    转义符统一转成 markdown 转义（`\\#`→`\\#`, `\\_`→`\\_`），
    避免在行首/表格行触发 markdown 语法（H1/斜体/表格分隔符）。
    """
    # 转义符：\# \& \_ \{ \} 保留为 markdown 转义形式（避免在行首/表格行触发 markdown 语法）
    # \% 直接转成字面 %（markdown 里 % 不是特殊字符，不需要转义）
    escapes = {r"\#": r"\#", r"\&": r"\&", r"\%": "%",
               r"\_": r"\_", r"\{": r"\{", r"\}": r"\}"}
    for cmd, sym in escapes.items():
        tex = tex.replace(cmd, sym)

    # 其他符号按长度降序 + 单词边界
    others = {k: v for k, v in _LATEX_SYMBOLS.items() if k not in escapes}
    for cmd in sorted(others, key=len, reverse=True):
        sym = others[cmd]
        tex = re.sub(re.escape(cmd) + r"(?![a-zA-Z])", sym, tex)
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
        fm.append(f'video_url: "{meta["url"]}"')
    if meta.get("channel"):
        fm.append(f'video_channel: "{meta["channel"]}"')
    if meta.get("duration"):
        fm.append(f'video_duration: "{meta["duration"]}"')
    pdf_name = tex_path.stem + ".pdf"
    fm.append("sources:")
    fm.append(f"  - {pdf_name}")
    fm.append("---")
    return "\n".join(fm)


# ---------------------------------------------------------------------------
# 主转换
# ---------------------------------------------------------------------------

def convert(tex_path: Path, md_path: Path) -> None:
    """主转换函数."""
    tex = tex_path.read_text(encoding="utf-8")

    # 1. 提取元数据
    meta = extract_metadata(tex)

    # 2. 保护数学公式
    body, math_store = protect_math(tex)

    # 3. 删除 preamble/titlepage/toc/newcommand 定义
    body = strip_latex_wrappers(body)

    # 4. 删除注释行
    body = strip_comments(body)

    # 5. 转换 quote/quotation/verse → blockquote（必须在 strip_latex_commands 前）
    body = convert_quote(body)

    # 6. 转换代码块 lstlisting（必须在 convert_lists 前，避免代码内 \item 被误切分）
    body = convert_lstlisting(body)

    # 7. 转换列表（itemize/enumerate）—— 必须在 strip_latex_commands 前
    body = convert_lists(body)

    # 8. 转换高亮框 → blockquote
    body = convert_tcolorbox(body)

    # 9. 跳过 TikZ / 图片占位 / 剩余 figure
    body = strip_tikz(body)
    body = convert_includegraphics(body)
    body = strip_remaining_figure_env(body)

    # 10. 章节标题 / 链接 / 脚注
    body = convert_sections(body)
    body = convert_href(body)
    body = convert_footnote(body)

    # 11. LaTeX 符号转 Unicode —— 必须在 strip_latex_commands 前
    body = convert_symbols(body)

    # 12. 清理剩余 LaTeX 命令
    body = strip_latex_commands(body)
    body = cleanup(body)

    # 13. 还原数学公式
    body = restore_math(body, math_store)
    body = cleanup(body)

    # 14. 组装 frontmatter + body（不再加 H1，布局组件会渲染标题）
    fm = build_frontmatter(meta, tex_path)
    md = f"{fm}\n\n{body}\n"

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
