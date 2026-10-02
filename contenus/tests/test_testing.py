import os

import pytest

from academy_content.testing import module_archive, parse_output
from conftest import make_module

IMAGE = os.environ.get("ROS_LAB_IMAGE")
needs_docker = pytest.mark.skipif(not IMAGE, reason="ROS_LAB_IMAGE non défini (tests Docker)")

SETUP = '#!/usr/bin/env bash\nset -e\nrm -rf "$WS"\nmkdir -p "$WS"\n'


def test_parse_output_all_steps_ok():
    out = "::etape:: setup ok\n::etape:: bug ok\n::etape:: solution ok\n::etape:: lab ok\n::fin::\n"
    r = parse_output("01-demo", out, 0)
    assert r.ok and [e.nom for e in r.etapes] == ["setup", "bug", "solution", "lab"]


def test_parse_output_failure_is_reported():
    out = "::etape:: setup ok\n::etape:: bug echec check.sh réussit alors que le bug est présent\n"
    r = parse_output("01-demo", out, 1)
    assert not r.ok
    assert "✘ check.sh échoue tant que le bug est présent — check.sh réussit alors que le bug est présent" in r.resume()


def test_parse_output_needs_end_marker():
    assert not parse_output("01-demo", "::etape:: setup ok\n", 0).ok


def test_archive_contains_module_and_course_files(tmp_path):
    import io, tarfile
    cours = "---\ntitre: T\n---\n```python fichier=src/p/p/n.py\nprint(1)\n```\n"
    base = make_module(tmp_path, **{"index.md": cours})
    with tarfile.open(fileobj=io.BytesIO(module_archive(base))) as tar:
        names = tar.getnames()
        assert "tmp/module/exercice/check.sh" in names
        assert tar.getmember("tmp/module/exercice/check.sh").mode == 0o755
        assert tar.extractfile("tmp/module/.cours/src/p/p/n.py").read() == b"print(1)\n"
        assert {m.uid for m in tar.getmembers()} == {1000}


@needs_docker
def test_good_module_passes(tmp_path):
    from academy_content.testing import run_module_tests
    base = make_module(tmp_path, **{"exercice/setup.sh": SETUP})
    r = run_module_tests(base, image=IMAGE)
    assert r.ok, r.journal


@needs_docker
def test_module_without_bug_is_rejected(tmp_path):
    from academy_content.testing import run_module_tests
    setup = SETUP + 'touch "$WS/ok"\n'  # le « bug » est déjà corrigé
    base = make_module(tmp_path, **{"exercice/setup.sh": setup})
    r = run_module_tests(base, image=IMAGE)
    assert not r.ok
    assert r.etapes[-1].nom == "bug" and not r.etapes[-1].ok


@needs_docker
def test_solution_that_does_not_fix_is_rejected(tmp_path):
    from academy_content.testing import run_module_tests
    base = make_module(tmp_path, **{"exercice/setup.sh": SETUP, "exercice/solution/ok": None,
                                     "exercice/solution/autre": "x\n"})
    r = run_module_tests(base, image=IMAGE)
    assert not r.ok and r.etapes[-1].nom == "solution"


@needs_docker
def test_lab_that_does_not_build_is_rejected(tmp_path):
    from academy_content.testing import run_module_tests
    base = make_module(tmp_path, **{
        "exercice/setup.sh": SETUP,
        "lab/src/casse/package.xml": (
            '<?xml version="1.0"?>\n<package format="3"><name>casse</name><version>0.0.0</version>'
            "<description>x</description><maintainer email='a@b.c'>a</maintainer><license>MIT</license>"
            "<buildtool_depend>ament_cmake</buildtool_depend><export><build_type>ament_cmake</build_type></export></package>\n"
        ),
        "lab/src/casse/CMakeLists.txt": "cmake_minimum_required(VERSION 3.8)\nproject(casse)\nfind_package(paquet_inexistant REQUIRED)\n",
    })
    r = run_module_tests(base, image=IMAGE)
    assert not r.ok and r.etapes[-1].nom == "lab", r.journal
