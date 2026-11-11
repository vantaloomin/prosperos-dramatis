import pytest

from dramatis import ai, local_only, profiles
from dramatis.formats.companion.providers.vault import MemoryVault


@pytest.fixture(autouse=True)
def own_home(tmp_path, monkeypatch):
    """Each test keeps its settings and library in its own folder, never the user's."""
    monkeypatch.setenv('DRAMATIS_HOME', str(tmp_path / 'home'))


@pytest.fixture(autouse=True)
def test_host(monkeypatch):
    """FastAPI's test client calls itself `testserver`: it counts as this computer in tests."""
    monkeypatch.setattr(local_only, 'LOCAL', local_only.LOCAL | {'testserver'})


@pytest.fixture(autouse=True)
def own_keyring(monkeypatch):
    """Keys go to a keyring of the test's own, never the user's."""
    found = MemoryVault()
    monkeypatch.setattr(profiles, 'VAULT', found)
    return found


@pytest.fixture
def model(monkeypatch):
    """A stand-in for the user's model: answers in order from `model.replies`, and keeps what it was asked."""
    class Model:
        def __init__(self):
            self.replies, self.asked = [], []

        def __call__(self, system, prompt):
            self.asked.append((system, prompt))
            return self.replies.pop(0)

    found = Model()
    monkeypatch.setattr(ai, 'complete', found)
    return found
