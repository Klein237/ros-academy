"""Dossiers personnels à quota : numéros de projet, montage vérifié, création du dossier."""

import os

import pytest

from rosacademy_hub import disque
from rosacademy_hub.disque import FS_XFLAG_PROJINHERIT, HomeError, prepare_home, project_id, quota_mount

MOUNTINFO = """\
22 1 8:1 / / rw,relatime shared:1 - ext4 /dev/sda1 rw
40 22 7:0 / /srv/ros-academy/homes rw,relatime shared:20 - xfs /dev/loop0 rw,attr2,inode64,prjquota
41 22 7:1 / /srv/sans-quota rw,relatime shared:21 - xfs /dev/loop1 rw,attr2,inode64,noquota
42 22 8:2 / /srv/ext4 rw,relatime shared:22 - ext4 /dev/sda2 rw,prjquota
"""


def test_project_ids_are_stable_and_distinct():
    assert project_id("u1") == 10_001
    assert project_id("u42") == 10_042
    assert project_id("it1234abcd") == project_id("it1234abcd") >= 2_000_000_000
    assert project_id("it1234abcd") != project_id("it1234abce")
    assert project_id("u1x") >= 2_000_000_000  # pas un étudiant


@pytest.fixture
def mountinfo(tmp_path):
    p = tmp_path / "mountinfo"
    p.write_text(MOUNTINFO)
    return str(p)


def test_quota_mount_requires_xfs_with_project_quotas(mountinfo, monkeypatch):
    monkeypatch.setattr(os.path, "realpath", lambda p: p)
    assert quota_mount("/srv/ros-academy/homes", mountinfo)[0] == "xfs"
    assert quota_mount("/srv/ros-academy/homes/u1", mountinfo)[0] == "xfs"
    with pytest.raises(HomeError, match="prjquota"):
        quota_mount("/srv/sans-quota", mountinfo)
    with pytest.raises(HomeError, match="ext4"):
        quota_mount("/srv/ext4", mountinfo)
    with pytest.raises(HomeError, match="XFS"):
        quota_mount("/srv/ros-academy", mountinfo)  # le dossier parent, sur la racine ext4


@pytest.fixture
def fs(tmp_path, monkeypatch):
    """Projets et propriétaires simulés (les vrais ioctl demandent un XFS ; voir les tests d'intégration)."""
    projects, owners = {}, {}

    def ident(fd):
        return os.fstat(fd).st_ino

    monkeypatch.setattr(disque, "get_project", lambda fd: projects.get(ident(fd), (0, 0)))
    monkeypatch.setattr(disque, "set_project", lambda fd, pid: projects.__setitem__(ident(fd), (FS_XFLAG_PROJINHERIT, pid)))
    monkeypatch.setattr(os, "fchown", lambda fd, u, g: owners.__setitem__(ident(fd), (u, g)))
    monkeypatch.setattr(os, "chown", lambda p, u, g: owners.__setitem__(os.stat(p).st_ino, (u, g)))
    skel = tmp_path / "skel"
    skel.mkdir()
    (skel / ".bashrc").write_text("# bashrc\n")
    (skel / "lien").symlink_to("/etc/passwd")
    root = tmp_path / "homes"
    root.mkdir()
    return root, skel, projects, owners


def test_new_home_gets_project_owner_and_skel(fs):
    root, skel, projects, owners = fs
    path = prepare_home(str(root), "u42", skel=str(skel))
    assert path == str(root / "u42")
    ino = os.stat(path).st_ino
    assert projects[ino] == (FS_XFLAG_PROJINHERIT, 10_042)
    assert owners[ino] == (1000, 1000)
    assert (root / "u42" / ".bashrc").read_text() == "# bashrc\n"
    assert not (root / "u42" / "lien").exists()  # seulement des fichiers ordinaires


def test_existing_home_is_kept_and_its_project_fixed(fs):
    root, skel, projects, owners = fs
    (root / "u7").mkdir()
    (root / "u7" / "travail.py").write_text("print(1)\n")
    prepare_home(str(root), "u7", skel=str(skel))
    assert projects[os.stat(root / "u7").st_ino] == (FS_XFLAG_PROJINHERIT, 10_007)
    assert (root / "u7" / "travail.py").read_text() == "print(1)\n"
    assert not (root / "u7" / ".bashrc").exists()  # le dossier n'est pas « réinitialisé »
    assert os.stat(root / "u7").st_ino not in owners


def test_unsafe_names_and_symlinked_homes_are_refused(fs, tmp_path):
    root, skel, _, _ = fs
    for name in ["../u1", "u1/x", "", ".cache", "U1", "a" * 65]:
        with pytest.raises(HomeError):
            prepare_home(str(root), name, skel=str(skel))
    (root / "u9").symlink_to(tmp_path)
    with pytest.raises(OSError):
        prepare_home(str(root), "u9", skel=str(skel))


def test_project_not_settable_is_an_explicit_error(fs, monkeypatch):
    root, skel, _, _ = fs

    def refuse(fd, pid):
        raise OSError(95, "Operation not supported")

    monkeypatch.setattr(disque, "set_project", refuse)
    with pytest.raises(HomeError, match="projet 10001 impossible"):
        prepare_home(str(root), "u1", skel=str(skel))
