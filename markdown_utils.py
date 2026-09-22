import re
import html
import markdown

try:
    import bleach
    HAS_BLEACH = True
except ImportError:
    HAS_BLEACH = False

ALLOWED_TAGS = [
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'p', 'ul', 'ol', 'li', 'blockquote',
    'pre', 'code', 'em', 'strong', 'del', 's', 'b', 'i',
    'a', 'table', 'thead', 'tbody', 'tr', 'th', 'td',
    'hr', 'br', 'span', 'div', 'sup', 'sub', 'details', 'summary', 'kbd'
]

ALLOWED_ATTRIBUTES = {
    '*': ['class', 'id'],
    'a': ['href', 'title', 'rel', 'target'],
    'code': ['class'],
    'th': ['align'],
    'td': ['align'],
}

ALLOWED_PROTOCOLS = ['http', 'https', 'mailto']


def _fallback_sanitize(html_content: str) -> str:
    """Safe fallback sanitizer when bleach is not available."""
    # Remove dangerous tags and their content
    dangerous_tags = ['script', 'style', 'iframe', 'object', 'embed', 'form', 'input', 'button']
    for tag in dangerous_tags:
        pattern = re.compile(rf'<{tag}\b[^>]*>.*?</{tag}>', re.IGNORECASE | re.DOTALL)
        html_content = pattern.sub('', html_content)
        pattern_self = re.compile(rf'<{tag}\b[^>]*/?>', re.IGNORECASE)
        html_content = pattern_self.sub('', html_content)

    # Strip dangerous event handlers (e.g. onload, onclick, onerror)
    event_handler_pattern = re.compile(r'\s+on[a-zA-Z]+\s*=\s*(["\'][^"\']*["\']|[^\s>]+)', re.IGNORECASE)
    html_content = event_handler_pattern.sub('', html_content)

    # Strip javascript: protocols in hrefs
    js_proto_pattern = re.compile(r'href\s*=\s*["\']?\s*javascript:[^"\'>\s]*["\']?', re.IGNORECASE)
    html_content = js_proto_pattern.sub('href="#"', html_content)

    return html_content


def sanitize_html(html_content: str) -> str:
    """Sanitize HTML ensuring only safe elements and attributes are rendered."""
    if HAS_BLEACH:
        cleaned = bleach.clean(
            html_content,
            tags=ALLOWED_TAGS,
            attributes=ALLOWED_ATTRIBUTES,
            protocols=ALLOWED_PROTOCOLS,
            strip=True
        )
    else:
        cleaned = _fallback_sanitize(html_content)

    # Add rel="noopener noreferrer" and target="_blank" for external links
    def link_replacer(match):
        full_tag = match.group(0)
        href_match = re.search(r'href=["\']([^"\']+)["\']', full_tag, re.IGNORECASE)
        if href_match:
            href = href_match.group(1)
            if href.startswith(('http://', 'https://')):
                if 'target=' not in full_tag:
                    full_tag = full_tag[:-1] + ' target="_blank" rel="noopener noreferrer">'
                elif 'rel=' not in full_tag:
                    full_tag = full_tag[:-1] + ' rel="noopener noreferrer">'
        return full_tag

    cleaned = re.sub(r'<a\b[^>]*>', link_replacer, cleaned)
    return cleaned


def render_markdown_with_toc(text: str):
    """Renders Markdown text into safe HTML and extracts the Table of Contents."""
    if not text:
        return "", ""

    md = markdown.Markdown(
        extensions=[
            'extra',
            'tables',
            'fenced_code',
            'codehilite',
            'toc',
            'sane_lists',
            'nl2br'
        ],
        extension_configs={
            'codehilite': {
                'linenums': False,
                'guess_lang': False,
                'css_class': 'highlight'
            },
            'toc': {
                'title': 'Table of Contents',
                'toc_depth': '2-4'
            }
        },
        output_format='html5'
    )

    raw_html = md.convert(text)
    sanitized_html = sanitize_html(raw_html)
    toc_html = sanitize_html(md.toc) if hasattr(md, 'toc') else ""
    if '<li' not in toc_html:
        toc_html = ""

    return sanitized_html, toc_html


def render_markdown(text: str) -> str:
    """Renders Markdown text into safe, sanitized HTML."""
    html_content, _ = render_markdown_with_toc(text)
    return html_content


def calculate_reading_time(text: str) -> int:
    """Calculate approximate reading time in minutes."""
    if not text:
        return 1
    # Strip basic markdown tokens to count words
    plain_text = re.sub(r'[#*`_~\[\]()\-+>!]', ' ', text)
    words = len(plain_text.split())
    minutes = max(1, round(words / 200))
    return minutes
