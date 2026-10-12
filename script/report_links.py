"""Resolve report links for Streamlit and portable HTML exports."""
import posixpath
import re
import unicodedata
from urllib.parse import quote, urlsplit

REPOSITORY = 'https://github.com/Phanuwatphk/Used-Phone-Price-Prediction'


def heading_anchor(heading):
    cleaned = ''.join(character for character in heading.strip().lower()
                      if character.isalnum() or character in ' -_'
                      or unicodedata.category(character).startswith('M'))
    return re.sub(r'\s', '-', cleaned)


def report_url(target, *, local_anchors=False):
    parsed = urlsplit(target)
    if parsed.scheme:
        return target if parsed.scheme in ('https', 'http', 'mailto') else None
    if not parsed.path:
        if local_anchors:
            return target
        path = 'docs/modeling.md'
    elif parsed.path.startswith(('tables/', 'figures/')) or parsed.path == 'metadata.json':
        path = 'docs/assets/modeling/' + parsed.path
    else:
        path = posixpath.normpath(posixpath.join('docs', parsed.path))
    if path.startswith('../') or path.startswith('/'):
        return None
    # JSON keys are not HTML anchors on GitHub; open the corresponding file.
    fragment = parsed.fragment if not path.endswith('.json') else ''
    return (REPOSITORY + '/blob/main/' + quote(path, safe='/')
            + ('#' + quote(fragment) if fragment else ''))


def website_report_links(markdown):
    def replace(match):
        url = report_url(match[2])
        return '[' + match[1] + '](' + url + ')' if url else match[1]
    return re.sub(r'(?<!!)\[([^\]]+)\]\(([^)]+)\)', replace, markdown)
