"""
知识库文档渐进式检索脚本

支持按步骤渐进式读取知识库文档，最小化上下文 token 消耗：
1. 读取目录文件（目录.md），获取所有页面列表
2. 读取功能概述文件，了解页面核心功能
3. 读取关键功能交互流程中的某个具体流程（按二级标题定位）
4. 读取可交互元素清单

用法:
  python kb_query.py <知识库目录> <命令> [参数]

命令:
  toc                          读取目录文件
  overview <页面名称>          读取功能概述
  headings <文件路径>          读取文件所有标题和行号
  section <文件路径> <标题>    读取文件中指定标题下的内容
  elements <页面名称>          读取可交互元素清单
  flows <页面名称>             读取关键功能交互流程的所有二级标题
  flow <页面名称> <流程名>     读取关键功能交互流程中指定流程的内容
"""

import sys
import re
import os
from pathlib import Path


def read_file_lines(filepath: str) -> list[str]:
    if not os.path.exists(filepath):
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return f.readlines()


def find_headings(lines: list[str], level: int = 2) -> list[dict]:
    results = []
    pattern = re.compile(r'^(#{1,6})\s+(.+)')
    for i, line in enumerate(lines, 1):
        m = pattern.match(line.strip())
        if m:
            heading_level = len(m.group(1))
            heading_text = m.group(2).strip()
            if level == 0 or heading_level == level:
                results.append({
                    "level": heading_level,
                    "title": heading_text,
                    "line": i,
                })
    return results


def extract_section(lines: list[str], title: str, include_subsections: bool = True) -> str:
    target_line = None
    target_level = None
    pattern = re.compile(r'^(#{1,6})\s+(.+)')

    for i, line in enumerate(lines):
        m = pattern.match(line.strip())
        if m and m.group(2).strip() == title:
            target_line = i
            target_level = len(m.group(1))
            break

    if target_line is None:
        return f"未找到标题: {title}"

    end_line = len(lines)
    for i in range(target_line + 1, len(lines)):
        m = pattern.match(lines[i].strip())
        if m:
            heading_level = len(m.group(1))
            if include_subsections:
                if heading_level <= target_level:
                    end_line = i
                    break
            else:
                if heading_level <= target_level + 1 and heading_level <= target_level:
                    end_line = i
                    break

    section_lines = lines[target_line:end_line]
    return "".join(section_lines).strip()


def cmd_toc(kb_dir: str):
    toc_path = os.path.join(kb_dir, "目录.md")
    if not os.path.exists(toc_path):
        alt_path = os.path.join(kb_dir, "目录.md")
        if not os.path.exists(alt_path):
            print(f"错误: 未找到目录文件 {toc_path}")
            return
    with open(toc_path, "r", encoding="utf-8") as f:
        print(f.read())


def cmd_overview(kb_dir: str, page_name: str):
    filepath = os.path.join(kb_dir, f"{page_name}_功能概述.md")
    if not os.path.exists(filepath):
        print(f"错误: 未找到文件 {filepath}")
        return
    with open(filepath, "r", encoding="utf-8") as f:
        print(f.read())


def cmd_headings(filepath: str):
    if not os.path.exists(filepath):
        print(f"错误: 未找到文件 {filepath}")
        return
    lines = read_file_lines(filepath)
    headings = find_headings(lines, level=0)
    if not headings:
        print("未找到任何标题")
        return
    for h in headings:
        indent = "  " * (h["level"] - 1)
        print(f"L{h['line']:>4}  {indent}{'#' * h['level']} {h['title']}")


def cmd_section(filepath: str, title: str):
    if not os.path.exists(filepath):
        print(f"错误: 未找到文件 {filepath}")
        return
    lines = read_file_lines(filepath)
    print(extract_section(lines, title, include_subsections=True))


def cmd_elements(kb_dir: str, page_name: str):
    filepath = os.path.join(kb_dir, f"{page_name}_可交互元素清单.md")
    if not os.path.exists(filepath):
        print(f"错误: 未找到文件 {filepath}")
        return
    with open(filepath, "r", encoding="utf-8") as f:
        print(f.read())


def cmd_flows(kb_dir: str, page_name: str):
    filepath = os.path.join(kb_dir, f"{page_name}_关键功能交互流程.md")
    if not os.path.exists(filepath):
        print(f"错误: 未找到文件 {filepath}")
        return
    lines = read_file_lines(filepath)
    headings = find_headings(lines, level=2)
    if not headings:
        print("未找到任何流程标题（二级标题）")
        return
    for h in headings:
        print(f"L{h['line']:>4}  {h['title']}")


def cmd_flow(kb_dir: str, page_name: str, flow_title: str):
    filepath = os.path.join(kb_dir, f"{page_name}_关键功能交互流程.md")
    if not os.path.exists(filepath):
        print(f"错误: 未找到文件 {filepath}")
        return
    lines = read_file_lines(filepath)
    print(extract_section(lines, flow_title, include_subsections=True))


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    kb_dir = sys.argv[1]
    command = sys.argv[2]

    if not os.path.isdir(kb_dir):
        print(f"错误: 目录不存在 {kb_dir}")
        sys.exit(1)

    if command == "toc":
        cmd_toc(kb_dir)
    elif command == "overview":
        if len(sys.argv) < 4:
            print("用法: python kb_query.py <知识库目录> overview <页面名称>")
            sys.exit(1)
        cmd_overview(kb_dir, sys.argv[3])
    elif command == "headings":
        if len(sys.argv) < 4:
            print("用法: python kb_query.py <知识库目录> headings <文件路径>")
            sys.exit(1)
        cmd_headings(sys.argv[3])
    elif command == "section":
        if len(sys.argv) < 5:
            print("用法: python kb_query.py <知识库目录> section <文件路径> <标题>")
            sys.exit(1)
        cmd_section(sys.argv[3], sys.argv[4])
    elif command == "elements":
        if len(sys.argv) < 4:
            print("用法: python kb_query.py <知识库目录> elements <页面名称>")
            sys.exit(1)
        cmd_elements(kb_dir, sys.argv[3])
    elif command == "flows":
        if len(sys.argv) < 4:
            print("用法: python kb_query.py <知识库目录> flows <页面名称>")
            sys.exit(1)
        cmd_flows(kb_dir, sys.argv[3])
    elif command == "flow":
        if len(sys.argv) < 5:
            print("用法: python kb_query.py <知识库目录> flow <页面名称> <流程标题>")
            sys.exit(1)
        cmd_flow(kb_dir, sys.argv[3], sys.argv[4])
    else:
        print(f"未知命令: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
