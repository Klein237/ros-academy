import logging

import pytest

from veille import CpuWindow, Settings, Watch, read_cpu, read_disk_percent, read_memory_percent


class Clock:
    def __init__(self):
        self.t = 1_000_000.0

    def __call__(self):
        return self.t


@pytest.fixture
def proc(tmp_path):
    def write(active, total, mem_avail_kb=8_000_000, mem_total_kb=16_000_000):
        idle = total - active
        # user nice system idle iowait irq softirq steal guest guest_nice
        (tmp_path / "stat").write_text(f"cpu  {active} 0 0 {idle} 0 0 0 0 0 0\ncpu0 1 2 3 4\n")
        (tmp_path / "meminfo").write_text(f"MemTotal: {mem_total_kb} kB\nMemFree: 1 kB\nMemAvailable: {mem_avail_kb} kB\n")
    write(0, 0)
    return tmp_path, write


def make(proc_dir, clock, services=None, http=None, **kw):
    mails = []
    s = Settings(proc=str(proc_dir), disks=(str(proc_dir),), services=services or {}, cpu_window=300,
                 reminder=3600, admins=("admin@exemple.fr",), **kw)
    w = Watch(s, mailer=lambda settings, subject, body: mails.append((subject, body)),
              http=http or (lambda url: (True, "HTTP 200")), clock=clock)
    return w, mails


def test_readers(proc, tmp_path):
    d, write = proc
    write(300, 1000, mem_avail_kb=4_000_000, mem_total_kb=16_000_000)
    assert read_cpu(str(d)) == (300, 1000)
    assert read_memory_percent(str(d)) == 75.0
    assert 0 <= read_disk_percent(str(tmp_path)) <= 100


def test_cpu_window_needs_a_full_window_and_averages():
    w = CpuWindow(300)
    w.add(0, 0, 0)
    w.add(100, 90, 100)
    assert w.percent() is None  # fenêtre pas encore remplie : pas d'alerte au démarrage
    w.add(300, 200, 300)
    assert w.percent() == pytest.approx(200 / 3)
    w.add(600, 500, 600)  # seuls les 300 dernières secondes comptent
    assert w.percent() == pytest.approx(100.0)


def test_cpu_alert_after_five_minutes_then_recovery_with_hysteresis(proc):
    d, write = proc
    clock = Clock()
    w, mails = make(d, clock, disk=101)
    active = total = 0
    for _ in range(21):  # 5 min à 90 %
        active, total = active + 90, total + 100
        write(active, total)
        w.tick()
        clock.t += 15
    assert [m[0] for m in mails] == ["[RoboForge] Alerte : CPU à 90 % (seuil 80 %)"]
    assert "https://localhost/admin/journaux/" in mails[0][1]
    for _ in range(25):  # 78 % : sous le seuil mais pas assez pour revenir à la normale
        active, total = active + 78, total + 100
        write(active, total)
        w.tick()
        clock.t += 15
    assert len(mails) == 1
    for _ in range(25):
        active, total = active + 50, total + 100
        write(active, total)
        w.tick()
        clock.t += 15
    assert mails[-1][0] == "[RoboForge] Retour à la normale : CPU" and len(mails) == 2


def test_memory_and_disk_alerts_with_reminder(proc):
    d, write = proc
    clock = Clock()
    write(0, 0, mem_avail_kb=2_000_000)  # 87,5 % de mémoire utilisée
    w, mails = make(d, clock, disk=0)  # seuil disque à 0 % : toujours en alerte
    w.tick()
    subjects = [m[0] for m in mails]
    assert "[RoboForge] Alerte : mémoire à 88 % (seuil 80 %)" in subjects
    assert any(s.startswith("[RoboForge] Alerte : disque à") for s in subjects)
    clock.t += 1800
    w.tick()
    assert len(mails) == 2  # pas de rappel avant 1 h
    clock.t += 1800
    w.tick()
    assert len([m for m in mails if "Toujours en alerte" in m[0]]) == 2


def test_service_down_after_three_failures_then_restored(proc):
    d, _ = proc
    clock = Clock()
    state = {"ok": False}
    w, mails = make(d, clock, services={"comptes": "http://comptes:8300/connexion"},
                    http=lambda url: (state["ok"], "ConnectionRefusedError"), disk=101)
    w.tick()
    w.tick()
    assert mails == []  # un redémarrage bref ne réveille personne
    w.tick()
    assert mails[-1][0] == "[RoboForge] Alerte : service comptes injoignable (ConnectionRefusedError)"
    w.tick()
    assert len(mails) == 1
    clock.t += 600
    state["ok"] = True
    w.tick()
    assert mails[-1][0] == "[RoboForge] Service rétabli : comptes" and "10 min" in mails[-1][1]


def test_alerts_are_logged_even_without_smtp_and_mail_errors_do_not_stop(proc, caplog):
    from veille import send_mail
    d, write = proc
    s = Settings(proc=str(d), disks=(str(d),), disk=0)
    caplog.set_level(logging.INFO, logger="veille")
    Watch(s, mailer=send_mail, clock=Clock()).tick()
    assert "ALERTE disque" in caplog.text and "E-mail d'alerte non envoyé" in caplog.text

    def broken(*a):
        raise OSError("smtp en panne")
    caplog.clear()
    Watch(s, mailer=broken, clock=Clock()).tick()
    assert "Envoi de l'alerte impossible (OSError)" in caplog.text


def test_unreadable_proc_is_reported_not_fatal(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="veille")
    s = Settings(proc=str(tmp_path / "absent"), disks=(str(tmp_path / "absent"),))
    Watch(s, mailer=lambda *a: None, clock=Clock()).tick()
    assert "Lecture de" in caplog.text and "Lecture du disque" in caplog.text


def test_settings_from_env():
    s = Settings.from_env({"VEILLE_SERVICES": "hub=http://hub:8000/hub/api, comptes=http://comptes:8300/connexion,bad",
                           "ADMIN_EMAILS": "a@x.fr, b@x.fr", "VEILLE_SEUIL_DISQUE": "1", "SMTP_PORT": "",
                           "DOMAIN": "academy.example"})
    assert s.services == {"hub": "http://hub:8000/hub/api", "comptes": "http://comptes:8300/connexion"}
    assert s.admins == ("a@x.fr", "b@x.fr") and s.disk == 1.0 and s.smtp_port == 587
    assert s.smtp_from == "RoboForge <no-reply@academy.example>"
