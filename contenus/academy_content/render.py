"""Markdown des cours → HTML.

Conventions d'écriture :
- ```python fichier=src/my_pkg/my_pkg/diff_drive_node.py : bloc contenant un fichier
  complet du lab guidé ; il reçoit un bouton « Ouvrir dans le lab » et sert aux tests
  (le lab guidé doit compiler avec ces fichiers) ;
- des blocs ```python et ```cpp qui se suivent sont présentés en onglets Python / C++.
"""

import html
import re
import shlex
from urllib.parse import quote

from markdown_it import MarkdownIt

TAB_LANGS = {"python": "Python", "cpp": "C++"}
LANG_LABELS = {
    "python": "Python", "cpp": "C++", "bash": "Terminal", "sh": "Terminal", "xml": "XML",
    "yaml": "YAML", "cmake": "CMake", "text": "Texte", "srv": "Service (.srv)", "action": "Action (.action)",
    "msg": "Message (.msg)",
}
SAFE_REL_RE = re.compile(r"^(?!/)(?!.*(?:^|/)\.\.?(?:/|$))[A-Za-z0-9_./+-]{1,255}$")


def parse_info(info):
    """« python fichier=src/a.py » → ("python", {"fichier": "src/a.py"})."""
    try:
        parts = shlex.split(info or "")
    except ValueError:
        parts = (info or "").split()
    if not parts:
        return "", {}
    attrs = {}
    for part in parts[1:]:
        key, sep, value = part.partition("=")
        if sep:
            attrs[key] = value
    return parts[0].lower(), attrs


def safe_rel_path(path):
    return path if path and SAFE_REL_RE.fullmatch(path) and "//" not in path else None


def _md():
    md = MarkdownIt("commonmark", {"html": False, "linkify": False, "typographer": False})
    md.enable(["table", "strikethrough"])
    return md


def code_files(markdown):
    """Fichiers complets déclarés dans le cours : {chemin relatif au workspace: contenu}."""
    files = {}
    for tok in _md().parse(markdown):
        if tok.type == "fence":
            _, attrs = parse_info(tok.info)
            path = safe_rel_path(attrs.get("fichier", ""))
            if path:
                files[path] = tok.content
    return files


def _group_tabs(tokens):
    """Marque les suites de blocs python/cpp consécutifs pour les afficher en onglets."""
    i = 0
    while i < len(tokens):
        j = i
        langs = []
        while j < len(tokens) and tokens[j].type == "fence":
            lang, _ = parse_info(tokens[j].info)
            if lang not in TAB_LANGS or lang in langs:
                break
            langs.append(lang)
            j += 1
        if len(langs) >= 2:
            for k in range(i, j):
                tokens[k].meta["tab"] = "first" if k == i else ("last" if k == j - 1 else "mid")
            i = j
        else:
            i += 1


def render_cours(markdown, module_id):
    md = _md()
    tokens = md.parse(markdown)
    _group_tabs(tokens)

    def fence(renderer, tokens, idx, options, env):
        tok = tokens[idx]
        lang, attrs = parse_info(tok.info)
        label = LANG_LABELS.get(lang, lang or "Code")
        path = safe_rel_path(attrs.get("fichier", ""))
        head = [f'<span class="code-lang">{html.escape(label)}</span>']
        if path:
            head.append(f'<code class="code-file">{html.escape(path)}</code>')
            href = f"/lab/?module={quote(module_id)}&open={quote(f'ws/{module_id}/{path}')}"
            head.append(f'<a class="code-open" href="{html.escape(href)}">Ouvrir dans le lab</a>')
        head.append('<button type="button" class="code-copy">Copier</button>')
        body = (
            f'<figure class="code" data-lang="{html.escape(lang)}" data-tab="{html.escape(TAB_LANGS.get(lang, ""))}">'
            f'<figcaption>{"".join(head)}</figcaption>'
            f'<pre><code class="language-{html.escape(lang)}">{html.escape(tok.content)}</code></pre></figure>\n'
        )
        tab = tok.meta.get("tab")
        if tab == "first":
            body = '<div class="code-tabs">' + body
        if tab == "last":
            body += "</div>\n"
        return body

    md.add_render_rule("fence", fence)
    return md.renderer.render(tokens, md.options, {})


def render_markdown(markdown):
    """Markdown simple (énoncé, indices, explication) : pas de boutons de lab."""
    return _md().render(markdown or "")
