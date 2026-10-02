"""Dossiers personnels des étudiants, limités à 1 Go par les quotas de projet XFS.

L'hôte est préparé une fois (scripts/preparer-hote.sh) : un système de fichiers XFS monté
avec `prjquota` sur LAB_HOMES_DIR, avec une limite **par défaut** pour tous les projets
(`xfs_quota -x -c 'limit -p -d bhard=1g …'`). Le Hub n'a alors besoin d'aucun droit
particulier : à la création du dossier d'un étudiant, il lui donne son numéro de projet
avec l'héritage (ioctl FS_IOC_FSSETXATTR, permis au propriétaire), et tout ce que
l'étudiant y écrit compte dans ce projet. `df ~` affiche alors la limite dans le lab.
"""

import fcntl
import logging
import os
import re
import shutil
import struct
import zlib

log = logging.getLogger(__name__)

FS_IOC_FSGETXATTR = 0x801C581F
FS_IOC_FSSETXATTR = 0x401C5820
FS_XFLAG_PROJINHERIT = 0x00000200
FSXATTR = struct.Struct("=IIIII8x")  # xflags, extsize, nextents, projid, cowextsize

STUDENT_UID = STUDENT_GID = 1000  # utilisateur « etudiant » de l'image ros-lab
USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
STUDENT_RE = re.compile(r"^u(\d{1,9})$")
QUOTA_OPTIONS = {"prjquota", "pquota", "pqnoenforce"}


class HomeError(Exception):
    pass


def project_id(username):
    """Numéro de projet stable : 10000 + id pour les étudiants (u42), sinon dérivé du nom."""
    m = STUDENT_RE.fullmatch(username)
    if m:
        return 10_000 + int(m.group(1))
    return 2_000_000_000 + zlib.crc32(username.encode()) % 1_000_000_000


def get_project(fd):
    xflags, _, _, projid, _ = FSXATTR.unpack(fcntl.ioctl(fd, FS_IOC_FSGETXATTR, bytes(FSXATTR.size)))
    return xflags, projid


def set_project(fd, projid):
    xflags, extsize, nextents, _, cow = FSXATTR.unpack(fcntl.ioctl(fd, FS_IOC_FSGETXATTR, bytes(FSXATTR.size)))
    fcntl.ioctl(fd, FS_IOC_FSSETXATTR, FSXATTR.pack(xflags | FS_XFLAG_PROJINHERIT, extsize, nextents, projid, cow))


def quota_mount(root, mountinfo="/proc/self/mountinfo"):
    """(type, options) du montage qui porte `root` ; HomeError si les quotas de projet n'y sont pas actifs."""
    root = os.path.realpath(root)
    best = None
    with open(mountinfo) as f:
        for line in f:
            left, _, right = line.partition(" - ")
            point = left.split()[4].replace("\\040", " ")
            fstype, _source, super_opts = (right.split() + ["", "", ""])[:3]
            if (root == point or root.startswith(point.rstrip("/") + "/")) and (best is None or len(point) > len(best[0])):
                best = (point, fstype, set(super_opts.split(",")))
    if best is None or best[1] != "xfs" or not best[2] & QUOTA_OPTIONS:
        found = f"{best[1]} ({','.join(sorted(best[2]))})" if best else "aucun montage"
        raise HomeError(f"{root} doit être un système de fichiers XFS monté avec prjquota "
                        f"(scripts/preparer-hote.sh) ; trouvé : {found}")
    return best[1], best[2]


def prepare_home(root, username, skel="/etc/skel"):
    """Crée (si besoin) le dossier de l'étudiant, rattaché à son projet ; retourne son chemin."""
    if not USERNAME_RE.fullmatch(username or ""):
        raise HomeError(f"nom d'utilisateur refusé pour un dossier personnel : {username!r}")
    path = os.path.join(root, username)
    created = False
    try:
        os.mkdir(path, 0o750)
        created = True
    except FileExistsError:
        pass
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        want = project_id(username)
        xflags, projid = get_project(fd)
        if projid != want or not xflags & FS_XFLAG_PROJINHERIT:
            if not created:
                log.warning("Dossier %s rattaché au projet %s (était %s) : seuls les nouveaux fichiers "
                            "compteront ; voir scripts/migrer-volumes.sh", path, want, projid)
            try:
                set_project(fd, want)
            except OSError as exc:
                raise HomeError(f"projet {want} impossible à poser sur {path} : {exc}") from exc
        if created:
            for name in sorted(os.listdir(skel)) if os.path.isdir(skel) else []:
                src = os.path.join(skel, name)
                if os.path.isfile(src) and not os.path.islink(src):
                    dst = os.path.join(path, name)
                    shutil.copyfile(src, dst)
                    os.chown(dst, STUDENT_UID, STUDENT_GID)
            os.fchown(fd, STUDENT_UID, STUDENT_GID)
    finally:
        os.close(fd)
    return path
