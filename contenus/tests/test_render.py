from academy_content.render import code_files, parse_info, render_cours, render_markdown, safe_rel_path

COURS = """\
# Titre

```python fichier=src/my_pkg/my_pkg/node.py
print("py")
```

```cpp fichier=src/my_pkg_cpp/src/node.cpp
int main() {}
```

Texte.

```bash
ros2 run my_pkg node
```

```python fichier=../../etc/passwd
x = 1
```
"""


def test_parse_info():
    assert parse_info("python fichier=src/a.py") == ("python", {"fichier": "src/a.py"})
    assert parse_info('cpp fichier="src/a b.cpp"') == ("cpp", {"fichier": "src/a b.cpp"})
    assert parse_info("") == ("", {})


def test_code_files_keep_only_safe_paths():
    assert code_files(COURS) == {
        "src/my_pkg/my_pkg/node.py": 'print("py")\n',
        "src/my_pkg_cpp/src/node.cpp": "int main() {}\n",
    }


def test_safe_rel_path():
    for bad in ["../x", "/abs", "a/../b", "a//b", "./a", "a/./b", "", "a b"]:
        assert safe_rel_path(bad) is None, bad
    assert safe_rel_path("src/my_pkg/setup.py") == "src/my_pkg/setup.py"


def test_render_tabs_buttons_and_escaping():
    html = render_cours(COURS, "02-noeud")
    assert html.count('<div class="code-tabs">') == 1  # python + cpp regroupés, pas le bash
    assert 'href="/lab/?module=02-noeud&amp;open=ws/02-noeud/src/my_pkg/my_pkg/node.py"' in html
    assert "print(&quot;py&quot;)" in html
    assert "etc/passwd" not in html.split("<code class=\"language-python\">x = 1")[0].split("figcaption")[-1]


def test_raw_html_is_not_rendered():
    html = render_markdown("<script>alert(1)</script>\n\n[x](javascript:alert(1))")
    assert "<script>" not in html
    assert 'href="javascript:' not in html
