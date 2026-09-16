import os
import re
import sys
import json


def minify_js(content: str) -> str:
    """简易JS压缩，不用于ld+json"""
    content = re.sub(r"/\*[\s\S]*?\*/", "", content)
    lines = []
    for line in content.splitlines():
        stripped = line.strip()
        if "//" in stripped:
            idx = stripped.find("//")
            before = stripped[:idx]
            if before.count('"') % 2 == 0 and before.count("'") % 2 == 0 and before.count("`") % 2 == 0:
                stripped = before
        lines.append(stripped)
    content = " ".join(lines)
    content = re.sub(r"\s+", " ", content)
    return content.strip()


def minify_css(content: str) -> str:
    """简易CSS压缩"""
    content = re.sub(r"/\*[\s\S]*?\*/", "", content)
    content = re.sub(r"\s+", " ", content)
    content = re.sub(r"\s*([{};:,>])\s*", r"\1", content)
    return content.strip()


def minify_html(content: str, oneline: bool = False) -> str:
    """
    修复版HTML压缩
    ✅oneline=True：外层HTML全部合并为一行
    ✅application/ld+json：尝试解析json并压缩为单行，解析失败回退原始文本
    ✅<pre>完整保留内部格式
    ✅style、普通内联script内部压缩
    """
    place_holder_template = "\x00__BLOCK_{idx}__\x00"
    blocks = []

    pattern_blocks = re.compile(r"(<(script|style|pre)\b[^>]*>)([\s\S]*?)(</\2\s*>)", re.IGNORECASE)

    def save_block(match):
        tag_start = match.group(1)
        tag_name = match.group(2).lower()
        inner_text = match.group(3)
        tag_end = match.group(4)

        has_src = bool(re.search(r'\bsrc\s*=', tag_start, re.IGNORECASE))
        is_ld_json = bool(re.search(r'type=["\']application/ld\+json["\']', tag_start, re.IGNORECASE))

        inner_processed = inner_text
        if tag_name == "style":
            inner_processed = minify_css(inner_text)
        elif tag_name == "script":
            if has_src:
                inner_processed = inner_text.strip()
            elif is_ld_json:
                # 尝试把JSON‑LD压缩成单行，解析失败回退原始内容防止页面损坏
                try:
                    json_obj = json.loads(inner_text)
                    inner_processed = json.dumps(json_obj, separators=(',', ':'), ensure_ascii=False)
                except json.JSONDecodeError:
                    inner_processed = inner_text.strip()
            else:
                inner_processed = minify_js(inner_text)
        elif tag_name == "pre":
            inner_processed = inner_text

        block_full = tag_start + inner_processed + tag_end
        blocks.append(block_full)
        idx = len(blocks) - 1
        return place_holder_template.format(idx=idx)

    # 步骤1：提取所有特殊块，替换占位符
    html_safe = pattern_blocks.sub(save_block, content)

    # 步骤2：移除HTML注释
    html_safe = re.sub(r"<!--[\s\S]*?-->", "", html_safe)

    # 步骤3：回填之前做外层空白压缩
    if oneline:
        html_safe = re.sub(r">\s+<", "><", html_safe)
        html_safe = re.sub(r"\s+", " ", html_safe)
        html_safe = html_safe.strip()
    else:
        html_safe = re.sub(r">\s+<", r">\n<", html_safe)
        lines = [line.strip() for line in html_safe.splitlines()]
        lines = [l for l in lines if l]
        html_safe = "\n".join(lines)

    # 步骤4：回填预处理完成的块，回填后不再做空白处理
    for idx, block_text in enumerate(blocks):
        ph = place_holder_template.format(idx=idx)
        html_safe = html_safe.replace(ph, block_text)

    return html_safe


def process_file(file_path: str, oneline: bool):
    suffix = os.path.splitext(file_path)[1].lower()
    with open(file_path, "r", encoding="utf-8") as f:
        raw = f.read()

    if suffix == ".js":
        result = minify_js(raw)
    elif suffix == ".css":
        result = minify_css(raw)
    elif suffix == ".html":
        result = minify_html(raw, oneline=oneline)
    else:
        return

    # 直接覆盖原文件
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(result)
    print(f"✅已覆盖: {file_path}")


def walk_dir(root_dir: str, oneline: bool):
    for root, _, files in os.walk(root_dir):
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext in {".html", ".css", ".js"}:
                full_path = os.path.join(root, fname)
                try:
                    process_file(full_path, oneline=oneline)
                except Exception as e:
                    print(f"❌处理失败 {full_path}: {e}")


if __name__ == "__main__":
    args = sys.argv[1:]
    oneline_mode = False
    if "--oneline" in args:
        oneline_mode = True
        args.remove("--oneline")

    print("⚠️警告：脚本直接覆盖源文件，请确认已经完整备份static目录！")
    if len(args) < 1:
        print("用法:")
        print("  可读版(保留标签换行，覆盖源文件): python build_ld_compress.py ./static")
        print("  生产单行上线版(ld+json也压缩单行，覆盖源文件): python build_ld_compress.py ./static --oneline")
    else:
        target_dir = args[0]
        if not os.path.isdir(target_dir):
            print(f"错误：{target_dir} 不是有效目录")
        else:
            walk_dir(target_dir, oneline=oneline_mode)
            print("\n🎉全部文件处理&覆盖完成")
