
import pytest
from pathlib import Path
from session_bench.core.config import ExperimentConfig


def test_config_from_yaml():
    """
    Test loading config from YAML.
    """
    config_path = Path("configs/examples/baseline.yaml")

    if not config_path.exists():
        pytest.skip("Example config not found")

    config = ExperimentConfig.from_yaml(config_path)

    assert config.name == "baseline_evaluation"
    assert config.strategy_class == "strategies.baseline.BaselineStrategy"
    assert config.run_issue_tests is True
    assert "model_name" in config.strategy_config


def test_config_validation_missing_strategy():
    """
    Test that validation catches missing strategy class.
    """
    config = ExperimentConfig(
        name="test",
        description="test config",
        strategy_class="",  # Missing!
        session_ids=[1, 2, 3]
    )

    errors = config.validate()

    assert len(errors) > 0
    assert any("No strategy class" in e for e in errors)


def test_config_validation_missing_sessions():
    """
    Test that validation catches missing session IDs.
    """
    config = ExperimentConfig(
        name="test",
        description="test",
        strategy_class="strategies.test.TestStrategy",
        session_ids=[]  # Empty!
    )

    errors = config.validate()

    assert any("No session IDs" in e for e in errors)


def test_config_to_dict():
    """
    Test config serialization.
    """
    config = ExperimentConfig(
        name="test",
        description="test",
        strategy_class="strategies.test.TestStrategy",
        strategy_config={"param": "value"},
        session_ids=[1, 2, 3]
    )

    config_dict = config.to_dict()

    assert config_dict['experiment']['name'] == "test"
    assert config_dict['dataset']['session_ids'] == [1, 2, 3]
    assert config_dict['strategy']['class'] == "strategies.test.TestStrategy"
    assert config_dict['strategy']['config']['param'] == "value"