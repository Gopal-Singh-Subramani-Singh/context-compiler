import tomllib
from pathlib import Path

import pytest

from contextc.errors import OptionalDependencyError
from contextc.optional import optional_dependency_available, require_optional


def test_missing_optional_dependency_has_actionable_typed_error() -> None:
    module = "contextc_test_dependency_that_does_not_exist"
    assert optional_dependency_available(module) is False
    with pytest.raises(OptionalDependencyError, match="install Context Compiler"):
        require_optional(feature="test feature", module=module, extra="test")


def test_model_target_extras_include_complete_chat_template_runtime() -> None:
    pyproject = Path(__file__).parents[1] / "pyproject.toml"
    configuration = tomllib.loads(pyproject.read_text())
    extras = configuration["project"]["optional-dependencies"]
    for target in ("qwen", "llama"):
        requirements = extras[target]
        assert any(requirement.startswith("transformers>=") for requirement in requirements)
        assert any(requirement.startswith("jinja2>=") for requirement in requirements)
