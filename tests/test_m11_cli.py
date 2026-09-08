from __future__ import annotations

import json

from contextc.cli.main import build_parser, main


def test_case_study_cli_surface_is_complete(capsys) -> None:
    parser = build_parser()
    for arguments in (
        ("case-study", "list"),
        ("case-study", "validate", "--all"),
        ("case-study", "extract-labels", "humanize-empty-natural-list"),
        ("case-study", "run", "--all"),
        ("case-study", "report"),
        ("case-study", "verify-determinism", "--all"),
    ):
        assert parser.parse_args(arguments).command == "case-study"

    assert main(("case-study", "list")) == 0
    output = json.loads(capsys.readouterr().out)
    assert len(output["tasks"]) == 8
    assert all(len(task["pre_fix_revision"]) == 40 for task in output["tasks"])
