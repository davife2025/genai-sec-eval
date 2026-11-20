import os

from secbench.env import load_dotenv


def test_dotenv_loads_and_real_env_wins(tmp_path, monkeypatch):
    f = tmp_path / ".env"
    f.write_text('# comment\nFOO_TEST=bar\nexport BAZ_TEST="quoted value"\nKEEP_TEST=from_file\n')
    monkeypatch.delenv("FOO_TEST", raising=False)
    monkeypatch.delenv("BAZ_TEST", raising=False)
    monkeypatch.setenv("KEEP_TEST", "from_shell")
    assert load_dotenv(f) is True
    assert os.environ["FOO_TEST"] == "bar"
    assert os.environ["BAZ_TEST"] == "quoted value"
    assert os.environ["KEEP_TEST"] == "from_shell"
    monkeypatch.delenv("FOO_TEST"); monkeypatch.delenv("BAZ_TEST")


def test_missing_dotenv_is_fine(tmp_path):
    assert load_dotenv(tmp_path / "nope") is False
