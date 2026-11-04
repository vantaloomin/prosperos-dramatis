import pytest

from dramatis import ai


@pytest.fixture(autouse=True)
def own_home(tmp_path, monkeypatch):
    """Each test keeps its settings and library in its own folder, never the user's."""
    monkeypatch.setenv('DRAMATIS_HOME', str(tmp_path / 'home'))


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
