from pathlib import Path

import pytest

from contextc.config import ProjectConfig, apply_cli_overrides, load_project_config
from contextc.errors import ConfigurationError


def test_default_config_has_stable_identity() -> None:
    assert ProjectConfig().identity == ProjectConfig().identity


def test_load_contextc_toml_and_apply_cli_precedence(tmp_path: Path) -> None:
    config_path = tmp_path / "contextc.toml"
    config_path.write_text("[contextc]\nmax_file_bytes = 20\ninclude_hidden = true\n")
    loaded = load_project_config(config_path)
    overridden = apply_cli_overrides(loaded, {"max_file_bytes": 30, "include_hidden": None})
    assert loaded.include_hidden is True
    assert overridden.max_file_bytes == 30
    assert overridden.include_hidden is True


def test_load_pyproject_table(tmp_path: Path) -> None:
    path = tmp_path / "pyproject.toml"
    path.write_text("[tool.contextc]\ncache_root = 'cache'\n")
    assert load_project_config(path).cache_root == "cache"


@pytest.mark.parametrize(
    "text",
    ["not toml =", "[contextc]\nunknown = 1", "[contextc]\nmax_file_bytes = 0"],
)
def test_invalid_configuration_is_typed(tmp_path: Path, text: str) -> None:
    path = tmp_path / "contextc.toml"
    path.write_text(text)
    with pytest.raises(ConfigurationError):
        load_project_config(path)


def test_invalid_cli_override_is_typed() -> None:
    with pytest.raises(ConfigurationError):
        apply_cli_overrides(ProjectConfig(), {"not_a_field": 1})


def test_source_fact_rules_load_from_contextc_toml(tmp_path: Path) -> None:
    config_path = tmp_path / "contextc.toml"
    config_path.write_text(
        """
[contextc]

[[contextc.source_rules]]
glob = "external/**"
trust_domain = "external_content"

[[contextc.source_rules]]
glob = "private/**"
sensitivity = "secret"
instruction_authority = "none"
""".strip()
        + "\n"
    )
    loaded = load_project_config(config_path)
    assert len(loaded.source_rules) == 2
    assert loaded.source_rules[0].glob == "external/**"
    assert loaded.source_rules[0].trust_domain.value == "external_content"
    assert loaded.source_rules[1].sensitivity.value == "secret"
    assert loaded.source_rules[1].instruction_authority.value == "none"
    assert loaded.identity == load_project_config(config_path).identity


def test_source_fact_rule_validation_is_strict(tmp_path: Path) -> None:
    config_path = tmp_path / "contextc.toml"
    config_path.write_text(
        """
[contextc]

[[contextc.source_rules]]
glob = "../escape/**"
sensitivity = "secret"
""".strip()
        + "\n"
    )
    with pytest.raises(ConfigurationError):
        load_project_config(config_path)


def test_source_fact_rules_reject_privilege_promotion(tmp_path: Path) -> None:
    config_path = tmp_path / "contextc.toml"
    config_path.write_text(
        """
[contextc]

[[contextc.source_rules]]
glob = "vendor/**"
trust_domain = "system_policy"
instruction_authority = "system"
""".strip()
        + "\n"
    )
    with pytest.raises(ConfigurationError):
        load_project_config(config_path)
