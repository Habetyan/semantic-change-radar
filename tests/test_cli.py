import json
import subprocess
import sys


def test_cli_writes_report_and_reports_input_errors(tmp_path):
    old, new, output = (tmp_path / name for name in ("old.md", "new.md", "comparison.json"))
    old.write_text("The plan includes 5 projects.", encoding="utf-8")
    new.write_text("The plan includes 10 projects.", encoding="utf-8")
    command = [sys.executable, "-m", "radar.cli", str(old), str(new), "--backend", "lexical"]
    result = subprocess.run(command + ["--output", str(output)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    report = json.loads(output.read_text())
    assert report["changes"][0]["status"] == "modified"
    old.unlink()
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 1
    assert "Comparison failed" in result.stderr


def test_cli_profile_is_forwarded(monkeypatch, tmp_path, capsys):
    from radar import cli

    old, new = tmp_path / "old.txt", tmp_path / "new.txt"
    old.write_text("before")
    new.write_text("after")
    received = {}

    def compare(before, after, **options):
        received.update(options)
        return {"configuration": options}

    monkeypatch.setattr(cli, "compare_documents", compare)
    for profile in ("baseline", "context", "groups", "verified"):
        monkeypatch.setattr(sys, "argv", ["radar", str(old), str(new), "--profile", profile])
        assert cli.main() == 0
        assert received == {"backend": "semantic", "profile": profile}
        assert json.loads(capsys.readouterr().out)["configuration"]["profile"] == profile
