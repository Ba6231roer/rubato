"""
Snapshot interceptor for playwright-cli snapshot commands.
Automatically extracts locators from snapshot output and writes to webui_cache.
"""

import logging
import os
import re
from datetime import date, datetime

import yaml

logger = logging.getLogger(__name__)

# Globally tracked system name (set by LLM declaration or derived from URL)
_current_system_name: str | None = None


def set_system_name(name: str) -> None:
    """Set the current system name for webui cache."""
    global _current_system_name
    _current_system_name = name
    logger.info("Cache system name set to: %s", name)


def get_system_name() -> str | None:
    """Get the current system name."""
    return _current_system_name


def detect_snapshot_command(command: str) -> bool:
    """Check if a shell command is a playwright-cli snapshot call."""
    cmd_stripped = command.strip()
    return bool(
        re.search(r'playwright-cli\s+snapshot\b', cmd_stripped)
        and '--filename' not in cmd_stripped
    )


def detect_system_declaration(command: str) -> str | None:
    """Detect SYSTEM: declaration in commands like echo 'SYSTEM: name' or similar."""
    match = re.search(r'SYSTEM:\s*([a-zA-Z_][a-zA-Z0-9_-]*)', command)
    if match:
        return match.group(1)
    return None


def extract_snapshot_info(
    stdout: str, project_root: str = '',
) -> tuple[str, str, str] | None:
    """Extract page URL, page title, and snapshot YAML path from snapshot stdout.

    Handles two formats:
    1. File link: [Snapshot](.playwright-cli/page-xxx.yml)
    2. Inline YAML: ### Snapshot\\n```yaml\\n...\\n```

    Returns (page_url, page_title, snapshot_yml_path) or None if not a snapshot stdout.
    """
    url_match = re.search(r'Page URL:\s*(.+)', stdout)
    title_match = re.search(r'Page Title:\s*(.+)', stdout)
    snapshot_match = re.search(r'\[Snapshot\]\((.+)\)', stdout)

    if not url_match:
        logger.warning(
            "Snapshot stdout missing 'Page URL:', raw_output_preview=%s",
            stdout[:300],
        )
        return None

    if snapshot_match:
        return (
            url_match.group(1).strip(),
            title_match.group(1).strip() if title_match else '',
            snapshot_match.group(1).strip(),
        )

    inline_match = re.search(
        r'### Snapshot\n```yaml\n(.*?)\n```', stdout, re.DOTALL,
    )
    if inline_match:
        inline_content = inline_match.group(1)
        snapshot_dir = os.path.join(project_root, '.playwright-cli')
        os.makedirs(snapshot_dir, exist_ok=True)

        ts = datetime.now().strftime('%Y-%m-%dT%H-%M-%S-') + \
            f'{datetime.now().microsecond // 1000:03d}Z'
        filename = f'page-{ts}.yml'

        with open(os.path.join(snapshot_dir, filename), 'w', encoding='utf-8') as f:
            f.write(inline_content)

        relative_path = os.path.join('.playwright-cli', filename)
        logger.info(
            "Inline snapshot extracted and saved to %s (%d bytes)",
            relative_path, len(inline_content),
        )
        return (
            url_match.group(1).strip(),
            title_match.group(1).strip() if title_match else '',
            relative_path,
        )

    logger.warning(
        "Snapshot stdout missing '[Snapshot](...)' and inline YAML, "
        "raw_output_preview=%s",
        stdout[:300],
    )
    return None


def url_to_page_name(url: str) -> str:
    """Convert URL path to a page name.

    Examples:
        /account/bankAccount -> account_bankAccount
        / -> index
        /user/profile -> user_profile
    """
    from urllib.parse import urlparse
    parsed = urlparse(url)
    path = parsed.path.strip('/')
    if not path:
        return 'index'
    # Convert hash routes too
    if parsed.fragment:
        hash_path = parsed.fragment.strip('/')
        if hash_path:
            path = hash_path
    # Replace non-alphanumeric chars with underscores
    parts = re.split(r'[/\\]', path)
    cleaned = [re.sub(r'[^a-zA-Z0-9]', '_', p).strip('_') for p in parts if p]
    name = '_'.join(cleaned)
    return name or 'index'


def url_to_system_name(url: str) -> str:
    """Derive system name from URL domain.

    Examples:
        https://fat1.baidu.com/... -> fat1_baidu_com
        https://example.com/... -> example_com
    """
    from urllib.parse import urlparse
    parsed = urlparse(url)
    domain = parsed.netloc or parsed.hostname or 'unknown'
    # Remove port if present
    domain = domain.split(':')[0]
    # Replace dots with underscores
    return domain.replace('.', '_')


def process_snapshot_stdout(stdout: str, project_root: str) -> tuple[int, str | None]:
    """Process a snapshot stdout and write webui cache.

    Returns (element_count, cache_file_path) or (0, None) if not a snapshot.
    """
    info = extract_snapshot_info(stdout, project_root)
    if not info:
        return 0, None

    page_url, page_title, snapshot_yml_path = info
    logger.info(
        "Snapshot info extracted: url=%s, page_name=%s, system=%s, yml=%s, cwd=%s",
        page_url, url_to_page_name(page_url),
        _current_system_name or url_to_system_name(page_url),
        snapshot_yml_path, os.getcwd(),
    )
    system_name = _current_system_name or url_to_system_name(page_url)
    page_name = url_to_page_name(page_url)

    # Build full path to the snapshot YAML file
    full_yml_path = os.path.join(project_root, snapshot_yml_path)
    if not os.path.exists(full_yml_path):
        logger.warning(
            "Snapshot file not found: %s, project_root=%s, snapshot_yml_path=%s",
            full_yml_path, project_root, snapshot_yml_path,
        )
        return 0, None

    # Parse the ARIA tree
    try:
        elements = parse_aria_tree(full_yml_path)
    except Exception as e:
        logger.error("Failed to parse snapshot YAML: %s", e)
        return 0, None

    if not elements:
        return 0, None

    # Generate cache YAML
    cache_yaml = generate_cache_yaml(system_name, page_name, page_url, page_title, elements)

    # Write cache file
    cache_dir = os.path.join(project_root, 'webui_cache', system_name)
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, f'{page_name}.yaml')

    with open(cache_file, 'w', encoding='utf-8') as f:
        f.write(cache_yaml)

    # Update INDEX.yaml
    update_index(project_root, system_name, page_name, page_url, page_title)

    return len(elements), cache_file


def parse_aria_tree(yml_path: str) -> list[dict]:
    """Parse a Playwright ARIA snapshot YAML and extract interactive elements.

    Returns list of dicts with keys: id, description, locator, action_type, usage, quality
    """
    with open(yml_path, 'r', encoding='utf-8') as f:
        content = f.read()

    elements = []
    seen_locators = set()

    # Parse line by line since it's indentation-based ARIA format
    for line in content.split('\n'):
        result = parse_aria_line(line)
        if result is None:
            continue

        locator, description, action_type, ref = result

        # Skip duplicates
        locator_key = locator
        if locator_key in seen_locators:
            continue
        seen_locators.add(locator_key)

        elem_id = f'elem_{ref}' if ref else f'elem_{len(elements) + 1}'
        quality = 'low' if '# NOTE: no accessible name' in description else 'high'

        elements.append({
            'id': elem_id,
            'description': description,
            'locator': locator,
            'action_type': action_type,
            'usage': description,
            'quality': quality,
        })

    if not elements:
        file_size = os.path.getsize(yml_path) if os.path.exists(yml_path) else -1
        logger.warning(
            "No interactive elements parsed from %s, file_size=%d bytes",
            yml_path, file_size,
        )
    return elements


INTERACTIVE_ROLES = {
    'button', 'textbox', 'link', 'combobox', 'checkbox', 'radio',
    'tab', 'menuitem', 'option', 'switch', 'spinbutton', 'searchbox',
    'slider', 'img',
}

ROLE_ACTION_MAP = {
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


def parse_aria_line(line: str) -> tuple[str, str, str, str] | None:
    """Parse a single line of ARIA snapshot YAML.

    Returns (locator, description, action_type, ref) or None if not an interactive element.
    """
    stripped = line.strip()
    if not stripped.startswith('- '):
        return None

    # Extract the content after "- "
    content = stripped[2:]

    # Extract role (first word)
    words = content.split()
    if not words:
        return None

    role = words[0].rstrip(':')

    if role not in INTERACTIVE_ROLES:
        return None

    # Extract accessible name (quoted text after role)
    name_match = re.search(r'"([^"]*)"', content)
    accessible_name = name_match.group(1) if name_match else ''

    # Extract ref
    ref_match = re.search(r'\[ref=e(\d+)\]', content)
    ref = ref_match.group(1) if ref_match else ''

    # Generate locator
    if accessible_name:
        # Escape single quotes in name for the locator
        escaped_name = accessible_name.replace("'", "\\'")
        locator = f"getByRole('{role}', {{ name: '{escaped_name}' }})"
        description = f'{_role_label(role)}: {accessible_name}'
    else:
        locator = f"getByRole('{role}')"
        description = f'{_role_label(role)}（无名称） # NOTE: no accessible name'

    action_type = ROLE_ACTION_MAP.get(role, 'click')

    return locator, description, action_type, ref


_ROLE_LABELS = {
    'button': '按钮',
    'textbox': '输入框',
    'searchbox': '搜索框',
    'combobox': '下拉框',
    'checkbox': '复选框',
    'radio': '单选框',
    'link': '链接',
    'tab': '标签页',
    'menuitem': '菜单项',
    'switch': '开关',
    'spinbutton': '数字输入',
    'slider': '滑块',
    'option': '选项',
    'img': '图片',
}


def _role_label(role: str) -> str:
    return _ROLE_LABELS.get(role, role)


def generate_cache_yaml(
    system_name: str,
    page_name: str,
    page_url: str,
    page_title: str,
    elements: list[dict],
) -> str:
    """Generate webui cache YAML content."""
    today = date.today().isoformat()
    lines = [
        f'page:',
        f'  system: {system_name}',
        f'  name: {page_name}',
        f'  url_patterns:',
        f'  - {page_url}',
        f'  description: {page_title}',
        f'elements:',
    ]

    for elem in elements:
        lines.append(f'- id: {elem["id"]}')
        lines.append(f'  description: "{elem["description"]}"')
        lines.append(f'  locator: "{elem["locator"]}"')
        lines.append(f'  action_type: {elem["action_type"]}')
        lines.append(f'  usage: {elem["usage"]}')

    lines.append(f'last_verified: "{today}"')
    lines.append(f'version: 1')

    return '\n'.join(lines) + '\n'


def update_index(
    project_root: str,
    system_name: str,
    page_name: str,
    page_url: str,
    page_title: str,
) -> None:
    """Update webui_cache/INDEX.yaml with new page entry."""
    index_path = os.path.join(project_root, 'webui_cache', 'INDEX.yaml')
    today = date.today().isoformat()

    if os.path.exists(index_path):
        with open(index_path, 'r', encoding='utf-8') as f:
            index_data = yaml.safe_load(f) or {}
    else:
        index_data = {}

    systems = index_data.get('systems', [])
    if systems is None:
        systems = []

    # Find or create system entry
    system_entry = None
    for s in systems:
        if s.get('name') == system_name:
            system_entry = s
            break

    if system_entry is None:
        system_entry = {
            'name': system_name,
            'description': '',
            'pages': [],
        }
        systems.append(system_entry)

    pages = system_entry.get('pages', [])
    if pages is None:
        pages = []

    # Check if page already exists
    page_exists = False
    for p in pages:
        if p.get('name') == page_name:
            p['last_verified'] = today
            page_exists = True
            break

    if not page_exists:
        pages.append({
            'name': page_name,
            'file': f'{system_name}/{page_name}.yaml',
            'url_patterns': [page_url],
            'description': page_title,
            'last_verified': today,
        })

    system_entry['pages'] = pages
    index_data['systems'] = systems

    with open(index_path, 'w', encoding='utf-8') as f:
        yaml.dump(index_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


logger.info("Snapshot interceptor loaded")
