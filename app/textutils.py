"""Markdown -> sicheres HTML, plus Slug-Erzeugung und Text-Auszuege."""
import re
import unicodedata

import bleach
import markdown as md_lib
from markdown.extensions.toc import TocExtension

# Erlaubte Tags im gerenderten HTML (alles andere wird entfernt)
_ALLOWED_TAGS = [
    'p', 'br', 'hr', 'div', 'span',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'strong', 'b', 'em', 'i', 'u', 's', 'del', 'ins', 'mark', 'sub', 'sup',
    'ul', 'ol', 'li',
    'blockquote', 'pre', 'code',
    'a', 'img',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
]

_ALLOWED_ATTRS = {
    '*': ['class', 'id'],
    'a': ['href', 'title', 'rel', 'target'],
    'img': ['src', 'alt', 'title', 'width', 'height'],
    'td': ['align'],
    'th': ['align'],
}

# Nur sichere URL-Schemata zulassen (kein javascript:)
_ALLOWED_PROTOCOLS = ['http', 'https', 'mailto', 'data']


def render_markdown(text):
    """Rendert Markdown zu bereinigtem, sicherem HTML."""
    if not text:
        return ''
    html = md_lib.markdown(
        text,
        extensions=[
            'fenced_code',
            'tables',
            'sane_lists',
            'nl2br',
            TocExtension(permalink=False),
        ],
        output_format='html5',
    )
    cleaned = bleach.clean(
        html,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRS,
        protocols=_ALLOWED_PROTOCOLS,
        strip=True,
    )
    # Externe Links in neuem Tab + gegen Tab-Nabbing absichern
    cleaned = bleach.linkify(
        cleaned,
        callbacks=[_external_link_attrs],
        skip_tags=['pre', 'code'],
    )
    return cleaned


def _external_link_attrs(attrs, new=False):
    href = attrs.get((None, 'href'), '')
    if href.startswith('http'):
        attrs[(None, 'target')] = '_blank'
        attrs[(None, 'rel')] = 'noopener noreferrer'
    return attrs


def slugify(value, fallback='seite'):
    """Erzeugt einen URL-tauglichen Slug aus einem Titel."""
    value = unicodedata.normalize('NFKD', value or '')
    value = value.encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value).strip().lower()
    value = re.sub(r'[-\s]+', '-', value)
    return value or fallback


def split_tags(value, limit=15):
    """Zerlegt einen Komma-String in saubere, eindeutige Tag-Namen."""
    if not value:
        return []
    seen = set()
    result = []
    for raw in value.replace(';', ',').split(','):
        name = re.sub(r'\s+', ' ', raw.strip()).lstrip('#').strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(name[:80])
        if len(result) >= limit:
            break
    return result


def highlight(text, query, length=180):
    """Kurzer Auszug rund um den Treffer, Suchbegriff mit <mark> hervorgehoben.
    Gibt sicheres HTML zurueck (Text wird escaped, nur <mark> eingefuegt)."""
    from markupsafe import escape, Markup
    plain = re.sub(r'[#*`_>\[\]!]', '', text or '')
    plain = re.sub(r'\s+', ' ', plain).strip()
    if not query:
        return Markup(str(escape(plain[:length])) + ('…' if len(plain) > length else ''))
    low = plain.lower()
    pos = low.find(query.lower())
    if pos == -1:
        return Markup(str(escape(plain[:length])) + ('…' if len(plain) > length else ''))
    start = max(0, pos - length // 3)
    end = min(len(plain), start + length)
    snippet = plain[start:end]
    # Treffer im Snippet markieren (case-insensitive, erste Fundstelle)
    s_low = snippet.lower()
    q_low = query.lower()
    out = []
    i = 0
    while True:
        j = s_low.find(q_low, i)
        if j == -1:
            out.append(str(escape(snippet[i:])))
            break
        out.append(str(escape(snippet[i:j])))
        out.append('<mark>' + str(escape(snippet[j:j + len(query)])) + '</mark>')
        i = j + len(query)
    prefix = '…' if start > 0 else ''
    suffix = '…' if end < len(plain) else ''
    return Markup(prefix + ''.join(out) + suffix)


def excerpt(text, length=200):
    """Kurzer Klartext-Auszug (ohne Markdown-Zeichen) fuer Suchtreffer/Listen."""
    if not text:
        return ''
    plain = re.sub(r'[#*`_>\[\]!]', '', text)
    plain = re.sub(r'\s+', ' ', plain).strip()
    return (plain[:length] + '…') if len(plain) > length else plain
