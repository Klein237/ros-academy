"""Image des labs absente : retéléchargée depuis le registre de la CI, sous son nom local."""

import threading

from docker.errors import ImageNotFound

from academy_content.image_lab import LabImage, split_tag


class FakeImages:
    def __init__(self, present=False, pull_error=None):
        self.present, self.pull_error = present, pull_error
        self.pulls, self.tags = [], []
        self.done = threading.Event()

    def get(self, name):
        if not self.present:
            raise ImageNotFound(name)

    def pull(self, repo, tag):
        self.pulls.append(f"{repo}:{tag}")
        try:
            if self.pull_error:
                raise self.pull_error
            images = self

            class Image:
                def tag(self, repo, tag):
                    images.tags.append(f"{repo}:{tag}")
                    images.present = True
            return Image()
        finally:
            self.done.set()


class FakeClient:
    def __init__(self, images):
        self.images = images


def wait_repair(lab):
    assert lab.lock.acquire(timeout=5)
    lab.lock.release()


def test_split_tag():
    assert split_tag("ros-lab:0.1.0") == ("ros-lab", "0.1.0")
    assert split_tag("ros-lab") == ("ros-lab", "latest")
    assert split_tag("hote:5000/ros-lab") == ("hote:5000/ros-lab", "latest")
    assert split_tag("ghcr.io/a/ros-lab:1.2") == ("ghcr.io/a/ros-lab", "1.2")


def test_present_image_is_left_alone():
    images = FakeImages(present=True)
    assert LabImage("ros-lab:0.1.0", "ghcr.io/a/ros-lab", lambda: FakeClient(images))() == (True, "ros-lab:0.1.0", "")
    assert images.pulls == []


def test_missing_image_is_pulled_and_tagged_once():
    images = FakeImages()
    lab = LabImage("ros-lab:0.1.0", "ghcr.io/a/ros-lab", lambda: FakeClient(images))
    present, name, note = lab()
    assert not present and "Téléchargement automatique depuis ghcr.io/a/ros-lab:0.1.0 en cours" in note
    wait_repair(lab)
    assert images.pulls == ["ghcr.io/a/ros-lab:0.1.0"] and images.tags == ["ros-lab:0.1.0"]
    assert lab() == (True, "ros-lab:0.1.0", "")


def test_failed_pull_is_reported_and_retried_later():
    now = [1000.0]
    images = FakeImages(pull_error=RuntimeError("denied"))
    lab = LabImage("ros-lab:0.1.0", "ghcr.io/a/ros-lab", lambda: FakeClient(images), clock=lambda: now[0])
    lab()
    wait_repair(lab)
    present, _, note = lab()
    assert not present and "a échoué (denied)" in note and images.pulls == ["ghcr.io/a/ros-lab:0.1.0"]
    now[0] += 601
    lab()
    wait_repair(lab)
    assert len(images.pulls) == 2


def test_without_registry_nothing_is_pulled():
    images = FakeImages()
    assert LabImage("ros-lab:0.1.0", "", lambda: FakeClient(images))() == (False, "ros-lab:0.1.0", "")
    assert images.pulls == []
