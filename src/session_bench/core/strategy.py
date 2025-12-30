from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any
from dataclasses import dataclass, field


@dataclass
class SessionContext:
    """
    Session state passed to strategies.
    Accumulates context across multiple issues in a session.
    """

    constraints: Dict[str, bool] = field(default_factory=dict)

    issues_completed: list = field(default_factory=list)

    patches_generated: list = field(default_factory=list)

    test_results: list = field(default_factory=list)

    extra: Dict[str, Any] = field(default_factory=dict)

    def add_issue_result(self, issue: Dict, patch: str, test_result: Dict):
        """Add completed issue to session context."""
        self.issues_completed.append({
            'instance_id': issue['instance_id'],
            'problem_statement': issue.get('problem_statement', ''),
            'files_modified': self._extract_files_from_patch(patch)
        })
        self.patches_generated.append(patch)
        self.test_results.append(test_result)

    @staticmethod
    def _extract_files_from_patch(patch: str) -> list:
        """Extract modified file paths from unified diff."""
        files = []
        for line in patch.split('\n'):
            if line.startswith('diff --git'):
                parts = line.split()
                if len(parts) >= 3:
                    file_path = parts[2].replace('a/', '')
                    files.append(file_path)
        return files


class Strategy(ABC):
    """
    Abstract base class for all evaluation strategies.
    The framework calls generate_patch() for each issue.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize strategy with configuration.

        Args:
            config: Strategy-specific configuration from YAML
        """
        self.config = config
        self._metrics = {
            'total_calls': 0,
            'total_tokens': 0,
            'total_time': 0.0
        }

    @abstractmethod
    def generate_patch(
            self,
            issue: Dict[str, Any],
            codebase_path: Path,
            session_context: SessionContext
    ) -> Dict[str, Any]:
        """
        Generate a patch to fix the given issue.

        Args:
            issue: SWE-bench issue dictionary containing:
                - instance_id: Unique identifier
                - problem_statement: Issue description
                - base_commit: Git commit hash
                - FAIL_TO_PASS: Tests that should pass after fix
                - PASS_TO_PASS: Tests that should continue passing

            codebase_path: Path to repository at base_commit
                Strategy can read any files from here

            session_context: Accumulated session state
                Contains previous issues, patches, constraints, etc.

        Returns:
            {
                'patch': str,              # Unified diff format
                'metadata': {
                    'tokens_used': int,    # Total tokens consumed
                    'time_elapsed': float, # Generation time in seconds
                    'model_calls': int,    # Number of LLM calls
                    # Strategy can add any other metrics:
                    'custom_metric': Any,
                    ...
                }
            }

        Raises:
            Exception: If patch generation fails
        """
        pass

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get accumulated metrics for this strategy.

        Returns:
            Dictionary of metrics tracked by this strategy
        """
        return self._metrics.copy()

    def reset_metrics(self):
        """Reset metrics (called at start of new session)."""
        self._metrics = {
            'total_calls': 0,
            'total_tokens': 0,
            'total_time': 0.0
        }

    def __repr__(self):
        return f"{self.__class__.__name__}(config={self.config})"