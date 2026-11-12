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
    """A stand-in for the user's model: answers in order from `model.replies`, and keeps what it was asked. The check
    for a secret in the fields others read (dramatis/leaks.py) is answered apart, in `model.judged`: from
    `model.leaks` when a test gives it answers, else with no leaks."""
    class Model:
        def __init__(self):
            self.replies, self.asked, self.leaks, self.judged = [], [], [], []

        def __call__(self, system, prompt):
            if '{"leaks"' in system:
                self.judged.append((system, prompt))
                return self.leaks.pop(0) if self.leaks else '{"leaks": []}'
            self.asked.append((system, prompt))
            return self.replies.pop(0)

    found = Model()
    monkeypatch.setattr(ai, 'complete', found)
    return found
