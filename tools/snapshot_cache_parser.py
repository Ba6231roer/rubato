import argparse
import os
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

try:
    import yaml
except ImportError:
    print("Error: PyYAML is required. Install with: pip install pyyaml", file=sys.stderr)
    sys.exit(1)


INTERACTIVE_ROLES = {
    'button', 'textbox', 'link', 'combobox', 'checkbox', 'radio',
    'tab', 'menuitem', 'option', 'switch', 'spinbutton', 'searchbox',
    'slider', 'img',
}

ROLE_TO_ACTION = {
    'button': 'click',
    'textbox': 'fill',
    'searchbox': 'fill',
    'combobox': 'select',
    'checkbox': 'click',
    'radio': 'click',
    'link': 'click',
    'tab': 'click',
    'menuitem': 'click',
    'switch': 'click',
    'spinbutton': 'fill',
    'slider': 'hover',
    'option': 'select',
    'img': 'click',
}

ROLE_CN = {
    'button': '按钮',
    'textbox': '输入框',
    'searchbox': '搜索框',
    'combobox': '下拉框',
    'checkbox': '复选框',
    'radio': '单选框',
    'link': '链接',
    'tab': '标签',
    'menuitem': '菜单项',
    'switch': '开关',
    'spinbutton': '微调按钮',
    'slider': '滑块',
    'option': '选项',
    'img': '图片',
}

VERB_CN = {
    'fill': '输入',
    'click': '点击',
    'select': '选择',
    'hover': '悬停',
}

WEBUI_CACHE_DIR = Path(os.path.dirname(os.path.abspath(__file__))) / '..' / 'webui_cache'

_LINE_PATTERN = re.compile(
    r'^\s*-\s+'
    r'(\w+)'
    r'(?:\s+"([^"]*)")?'
    r'(.*)$'
)

_REF_PATTERN = re.compile(r'\[ref=([^\]]+)\]')


def parse_stdout(stdout_text):
    page_url = None
    page_title = None
    snapshot_yml_path = None

    for line in stdout_text.strip().split('\n'):
        stripped = line.strip()
        if stripped.startswith('- Page URL:'):
            page_url = stripped.split('- Page URL:', 1)[1].strip()
        elif stripped.startswith('- Page Title:'):
            page_title = stripped.split('- Page Title:', 1)[1].strip()
        elif '[Snapshot]' in stripped:
            match = re.search(r'\(([^)]+)\)', stripped)
            if match:
                snapshot_yml_path = match.group(1).strip()

    return page_url, page_title, snapshot_yml_path


def parse_aria_snapshot(file_path):
    elements = []

    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    for line in lines:
        match = _LINE_PATTERN.match(line)
        if not match:
            continue

        role = match.group(1).lower()
        if role not in INTERACTIVE_ROLES:
            continue

        name = match.group(2) or ''
        attrs = match.group(3) or ''

        ref_match = _REF_PATTERN.search(attrs)
        ref = ref_match.group(1) if ref_match else ''

        elements.append({
            'role': role,
            'name': name,
            'ref': ref,
        })

    return elements


def build_locator(role, name):
    if name:
        return f"getByRole('{role}', {{ name: '{name}' }})"
    return f"getByRole('{role}')"


def deduplicate_elements(elements):
    seen = {}
    result = []

    for elem in elements:
        locator = build_locator(elem['role'], elem['name'])
        if locator not in seen:
            seen[locator] = True
            result.append(elem)

    return result


def derive_system_name(page_url, provided_name=None):
    if provided_name:
        return provided_name

    parsed = urlparse(page_url)
    hostname = parsed.hostname or ''
    return hostname.replace('.', '_').replace('-', '_')


def derive_page_name(page_url):
    parsed = urlparse(page_url)
    path = parsed.path.strip('/')
    if not path:
        return 'index'

    segments = path.split('/')
    return '_'.join(segments)


def make_description(role, name):
    role_cn = ROLE_CN.get(role, role)
    if name:
        return f"{role_cn}: {name}"
    return f"{role_cn}（无名称）"


def make_usage(role, name, action_type):
    role_cn = ROLE_CN.get(role, role)
    verb_cn = VERB_CN.get(action_type, action_type)
    if name:
        return f"{verb_cn} {name} {role_cn}"
    return f"{verb_cn} {role_cn}"


def build_cache_yaml(system_name, page_name, page_url, page_title, elements, today_str):
    elem_list = []
    for i, elem in enumerate(elements):
        role = elem['role']
        name = elem['name']
        action_type = ROLE_TO_ACTION.get(role, 'click')

        desc = make_description(role, name)
        locator = build_locator(role, name)
        usage = make_usage(role, name, action_type)

        if not name:
            desc = f"{desc}  # NOTE: no accessible name"

        elem_list.append({
            'id': f"elem_{i + 1}",
            'description': desc,
            'locator': locator,
            'action_type': action_type,
            'usage': usage,
        })

    return {
        'page': {
            'system': system_name,
            'name': page_name,
            'url_patterns': [page_url],
            'description': page_title or '',
        },
        'elements': elem_list,
        'last_verified': today_str,
        'version': 1,
    }


def read_index(index_path):
    if not index_path.exists():
        return {'systems': []}

    with open(index_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    if data is None:
        return {'systems': []}
    if 'systems' not in data or data['systems'] is None:
        data['systems'] = []
    return data


def write_index(index_path, data):
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write("# webui_cache/INDEX.yaml\n")
        f.write("# WebUI 页面缓存索引\n")
        f.write("# 列出所有已缓存的被测系统和页面。\n")
        f.write("# test_case_executor 角色应在任务开始时读取此文件，了解可用的缓存。\n")
        f.write("\n")
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def update_index(system_name, page_name, page_url, page_title, today_str, cache_dir):
    index_path = cache_dir / 'INDEX.yaml'
    index = read_index(index_path)

    system_entry = None
    for s in index['systems']:
        if s.get('name') == system_name:
            system_entry = s
            break

    if system_entry is None:
        parsed = urlparse(page_url)
        base_url = f"{parsed.scheme}://{parsed.hostname}"
        system_entry = {
            'name': system_name,
            'description': '',
            'base_url': base_url,
            'pages': [],
        }
        index['systems'].append(system_entry)

    page_entry = None
    for p in system_entry.get('pages', []):
        if p.get('name') == page_name:
            page_entry = p
            break

    if page_entry is None:
        page_entry = {
            'name': page_name,
            'file': f"{system_name}/{page_name}.yaml",
            'url_patterns': [page_url],
            'description': page_title or '',
            'last_verified': today_str,
        }
        system_entry.setdefault('pages', []).append(page_entry)
    else:
        page_entry['last_verified'] = today_str
        if page_url not in page_entry.get('url_patterns', []):
            page_entry.setdefault('url_patterns', []).append(page_url)

    write_index(index_path, index)


def write_cache_file(cache_dir, system_name, page_name, data):
    system_dir = cache_dir / system_name
    system_dir.mkdir(parents=True, exist_ok=True)

    file_path = system_dir / f"{page_name}.yaml"
    with open(file_path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    return file_path


def parse_snapshot_stdout(stdout_text, system_name=None, stdout_file_dir=None):
    page_url, page_title, snapshot_yml_path = parse_stdout(stdout_text)

    if not page_url:
        raise ValueError("Could not find Page URL in stdout")
    if not snapshot_yml_path:
        raise ValueError("Could not find snapshot YAML path in stdout")

    snapshot_path = Path(snapshot_yml_path)
    if not snapshot_path.is_absolute():
        base_dir = Path(stdout_file_dir) if stdout_file_dir else Path.cwd()
        snapshot_path = base_dir / snapshot_path

    if not snapshot_path.exists():
        raise FileNotFoundError(f"Snapshot YAML file not found: {snapshot_path}")

    elements = parse_aria_snapshot(str(snapshot_path))
    elements = deduplicate_elements(elements)

    derived_system = derive_system_name(page_url, system_name)
    page_name = derive_page_name(page_url)
    today_str = date.today().isoformat()

    cache_data = build_cache_yaml(derived_system, page_name, page_url, page_title, elements, today_str)

    file_path = write_cache_file(WEBUI_CACHE_DIR, derived_system, page_name, cache_data)
    update_index(derived_system, page_name, page_url, page_title, today_str, WEBUI_CACHE_DIR)

    rel_path = os.path.relpath(file_path, start=os.path.dirname(file_path) if file_path else '.')
    return derived_system, page_name, len(elements), str(file_path)


def main():
    parser = argparse.ArgumentParser(
        description='Parse playwright-cli snapshot stdout and cache interactive elements'
    )
    parser.add_argument(
        'stdout_file',
        help='Path to file containing snapshot stdout'
    )
    parser.add_argument(
        '--system', '-s',
        dest='system_name',
        default=None,
        help='System name (derived from domain if not provided)'
    )

    args = parser.parse_args()

    stdout_path = Path(args.stdout_file)
    if not stdout_path.exists():
        print(f"Error: File not found: {args.stdout_file}", file=sys.stderr)
        sys.exit(1)

    try:
        stdout_text = stdout_path.read_text(encoding='utf-8')
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        system_name, page_name, count, file_path = parse_snapshot_stdout(
            stdout_text,
            system_name=args.system_name,
            stdout_file_dir=str(stdout_path.parent)
        )
        rel_path = os.path.relpath(file_path, start=Path.cwd())
        print(f"Cached {count} elements to {rel_path}")
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error: Invalid YAML in snapshot or index file: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
