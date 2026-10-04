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
import unicodedata
from urllib.parse import quote

from markdown_it import MarkdownIt

TAB_LANGS = {"python": "Python", "cpp": "C++"}
# Blocs de commandes : « Lancer dans le lab » quand le lab est ouvert à côté du cours (site.js)
COMMAND_LANGS = {"bash", "sh", "shell", "console"}
LANG_LABELS = {
    "python": "Python", "cpp": "C++", "bash": "Terminal", "sh": "Terminal", "xml": "XML",
    "yaml": "YAML", "cmake": "CMake", "text": "Texte", "srv": "Service (.srv)", "action": "Action (.action)",
    "msg": "Message (.msg)",
}
SAFE_REL_RE = re.compile(r"^(?!/)(?!.*(?:^|/)\.\.?(?:/|$))[A-Za-z0-9_./+-]{1,255}$")


def lab_link(module_id, **params):
    """Lien vers le lab, en passant par Comptes (connexion, quota, jeton du Hub)."""
    query = "&".join(f"{k}={quote(str(v), safe='/')}" for k, v in {"module": module_id, **params}.items())
    return "/compte/lab?suite=" + quote(f"/lab/?{query}", safe="/")


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


def _slug(text, used):
    text = text.lower().replace("œ", "oe").replace("æ", "ae")
    base = re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()).strip("-")
    base = "c-" + (base[:60] or "section")
    slug, n = base, 2
    while slug in used:
        slug, n = f"{base}-{n}", n + 1
    used.add(slug)
    return slug


def _prepare(md, markdown):
    """Jetons du cours : sans le titre de niveau 1 du début (déjà affiché par la page),
    avec un identifiant sur chaque titre de section (## …) pour le sommaire."""
    tokens = md.parse(markdown)
    if len(tokens) >= 3 and tokens[0].type == "heading_open" and tokens[0].tag == "h1":
        tokens = tokens[3:]
    used, sections = set(), []
    for i, tok in enumerate(tokens):
        if tok.type == "heading_open" and tok.tag == "h2":
            inline = tokens[i + 1]
            title = "".join(c.content for c in inline.children or [] if c.type in ("text", "code_inline")) or inline.content
            tok.attrSet("id", _slug(title, used))
            sections.append({"id": tok.attrGet("id"), "titre": title})
    return tokens, sections


def cours_sommaire(markdown):
    """Sections du cours (titres ## …) : [{"id", "titre"}], dans l'ordre."""
    return _prepare(_md(), markdown)[1]


def render_cours(markdown, module_id):
    md = _md()
    tokens, _ = _prepare(md, markdown)
    _group_tabs(tokens)

    def fence(renderer, tokens, idx, options, env):
        tok = tokens[idx]
        lang, attrs = parse_info(tok.info)
        label = LANG_LABELS.get(lang, lang or "Code")
        path = safe_rel_path(attrs.get("fichier", ""))
        head = [f'<span class="code-lang">{html.escape(label)}</span>']
        if path:
            head.append(f'<code class="code-file">{html.escape(path)}</code>')
            href = lab_link(module_id, open=f"ws/{module_id}/{path}")
            head.append(f'<a class="code-open" href="{html.escape(href)}" '
                        f'data-open="{html.escape(f"ws/{module_id}/{path}")}">Ouvrir dans le lab</a>')
        elif lang in COMMAND_LANGS:
            head.append('<button type="button" class="code-run" hidden>Lancer dans le lab</button>')
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
