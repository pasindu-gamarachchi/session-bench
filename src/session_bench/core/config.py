from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional
import yaml


@dataclass
class ExperimentConfig:

    name: str
    description: str
    random_seed: int = 42

    sessions_file: Path = Path("data/evaluation_sessions.json")
    session_ids: List[int] = field(default_factory=list)

    strategy_class: str = ""
    strategy_config: Dict[str, Any] = field(default_factory=dict)

    run_issue_tests: bool = True
    run_regression_tests: bool = True
    run_random_sample: bool = False
    random_sample_size: int = 20
    random_sample_unrelated_only: bool = True
    test_timeout: int = 300  # seconds

    check_orm_usage: bool = True
    check_view_patterns: bool = True
    check_naming_convention: bool = True

    workspace_dir: Path = Path("./workspaces")
    keep_workspaces: bool = False
    save_checkpoints: bool = True

    results_dir: Path = Path("./results")
    save_detailed_json: bool = True
    save_patches: bool = True
    save_logs: bool = True
    log_level: str = "INFO"

    retry_transient_errors: bool = True
    max_retries: int = 3
    retry_delay: int = 2

    extra_config: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, config_path: Path) -> 'ExperimentConfig':
        with open(config_path, 'r') as f:
            data = yaml.safe_load(f)

        experiment = data.get('experiment', {})
        dataset = data.get('dataset', {})
        strategy = data.get('strategy', {})
        testing = data.get('testing', {})
        constraints = data.get('constraints', {})
        workspace = data.get('workspace', {})
        output = data.get('output', {})
        error_handling = data.get('error_handling', {})

        return cls(
            name=experiment.get('name', 'unnamed_experiment'),
            description=experiment.get('description', ''),
            random_seed=experiment.get('random_seed', 42),

            sessions_file=Path(dataset.get('sessions_file', 'data/evaluation_sessions.json')),
            session_ids=dataset.get('session_ids', []),

            strategy_class=strategy.get('class', ''),
            strategy_config=strategy.get('config', {}),
            run_issue_tests=testing.get('run_issue_tests', True),
            run_regression_tests=testing.get('run_regression_tests', True),
            run_random_sample=testing.get('run_random_sample', False),
            random_sample_size=testing.get('random_sample_size', 20),
            random_sample_unrelated_only=testing.get('random_sample_unrelated_only', True),
            test_timeout=testing.get('test_timeout', 300),

            check_orm_usage=constraints.get('check_orm_usage', True),
            check_view_patterns=constraints.get('check_view_patterns', True),
            check_naming_convention=constraints.get('check_naming_convention', True),

            workspace_dir=Path(workspace.get('base_dir', './workspaces')),
            keep_workspaces=workspace.get('keep_workspaces', False),
            save_checkpoints=workspace.get('save_checkpoints', True),

            results_dir=Path(output.get('results_dir', './results')),
            save_detailed_json=output.get('save_detailed_json', True),
            save_patches=output.get('save_patches', True),
            save_logs=output.get('save_logs', True),
            log_level=output.get('log_level', 'INFO'),

            retry_transient_errors=error_handling.get('retry_transient_errors', True),
            max_retries=error_handling.get('max_retries', 3),
            retry_delay=error_handling.get('retry_delay', 2),

            extra_config={
                **data.get('extra', {}),
                **{k: v for k, v in data.items()
                   if k not in ['experiment', 'dataset', 'strategy', 'testing',
                                'constraints', 'workspace', 'output', 'error_handling']}
            }
        )

    def validate(self) -> List[str]:
        """Validate configs and return any errors"""
        errors = []

        if not self.strategy_class:
            errors.append("No strategy class specified in config")

        if not self.sessions_file.exists():
            errors.append(f"Sessions file not found: {self.sessions_file}")

        if not self.session_ids:
            errors.append("No session IDs specified")

        try:
            self.workspace_dir.mkdir(parents=True, exist_ok=True)
            self.results_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            errors.append(f"Cannot create directories: {e}")

        valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR']
        if self.log_level not in valid_log_levels:
            errors.append(f"Invalid log level: {self.log_level}")

        return errors

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {
            'experiment': {
                'name': self.name,
                'description': self.description,
                'random_seed': self.random_seed
            },
            'dataset': {
                'sessions_file': str(self.sessions_file),
                'session_ids': self.session_ids
            },
            'strategy': {
                'class': self.strategy_class,
                'config': self.strategy_config
            },
            'testing': {
                'run_issue_tests': self.run_issue_tests,
                'run_regression_tests': self.run_regression_tests,
                'run_random_sample': self.run_random_sample,
                'random_sample_size': self.random_sample_size,
                'random_sample_unrelated_only': self.random_sample_unrelated_only,
                'test_timeout': self.test_timeout
            },
            'constraints': {
                'check_orm_usage': self.check_orm_usage,
                'check_view_patterns': self.check_view_patterns,
                'check_naming_convention': self.check_naming_convention
            },
            'workspace': {
                'base_dir': str(self.workspace_dir),
                'keep_workspaces': self.keep_workspaces,
                'save_checkpoints': self.save_checkpoints
            },
            'output': {
                'results_dir': str(self.results_dir),
                'save_detailed_json': self.save_detailed_json,
                'save_patches': self.save_patches,
                'save_logs': self.save_logs,
                'log_level': self.log_level
            },
            'error_handling': {
                'retry_transient_errors': self.retry_transient_errors,
                'max_retries': self.max_retries,
                'retry_delay': self.retry_delay
            },
            **self.extra_config
        }