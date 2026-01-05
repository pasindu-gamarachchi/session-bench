import importlib
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging
import time

from session_bench.core.config import ExperimentConfig
from session_bench.core.strategy import Strategy, SessionContext
from session_bench.repository.manager import RepositoryManager
from session_bench.evaluation.constraints import ConstraintManager
from session_bench.evaluation.degradation import DegradationDetector
from session_bench.evaluation.testing import TestExecutor

logger = logging.getLogger(__name__)


class SessionEvaluator:
    """
    Main orchestrator for Session-Bench evaluations.

    Coordinates:
    - Strategy loading
    - Repository management
    - Test execution
    - Constraint checking
    - Degradation detection
    - Results collection

    Usage:
        config = ExperimentConfig.from_yaml("config.yaml")
        evaluator = SessionEvaluator(config)

        results = evaluator.run_session(session_data)
    """

    def __init__(self, config: ExperimentConfig):
        """
        Initialize session evaluator.
        Args:
            config: Experiment configuration
        """
        self.config = config

        # init components
        self.repo_manager = RepositoryManager(config.workspace_dir)
        self.constraint_manager = ConstraintManager(config.extra_config.get('constraints', {}))
        self.degradation_detector = DegradationDetector(config.extra_config.get('degradation', {}))
        self.test_executor = TestExecutor({
            'run_issue_tests': config.run_issue_tests,
            'run_regression_tests': config.run_regression_tests,
            'run_random_sample': config.run_random_sample,
            'random_sample_size': config.random_sample_size,
            'test_timeout': config.test_timeout
        })
        self.strategy: Optional[Strategy] = None

        logger.info("SessionEvaluator initialized")

    def run_session(self, session: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run a complete evaluation session.
        Args:
            session: Session data
        Returns:
            Eval results
        """
        session_id = session['session_id']
        repo_url = session['repo_url']
        base_commit = session['base_commit']
        issues = session['issues']

        logger.info(f"-" * 80)
        logger.info(f"Starting session {session_id} with {len(issues)} issues")
        logger.info(f"-" * 80)

        session_start_time = time.time()

        self.strategy = self._load_strategy()

        workspace_path = self.repo_manager.setup_repository(session_id=str(session_id), repo_url=repo_url,
                                                            base_commit=base_commit)

        session_context = SessionContext(
            constraints={
                'check_orm_usage': self.config.check_orm_usage,
                'check_view_patterns': self.config.check_view_patterns,
                'check_naming_convention': self.config.check_naming_convention
            }
        )

        self.degradation_detector.reset()

        session_results = {
            'session_id': session_id,
            'strategy': self.config.strategy_class,
            'degraded': False,
            'issues_completed': 0,
            'degradation_signal': None,
            'issues': [],
            'total_tokens': 0,
            'total_time': 0.0
        }

        for issue_number, issue in enumerate(issues, start=1):
            logger.info(f"\n{'-' * 80}")
            logger.info(f"Issue {issue_number} of {len(issues)}: {issue['instance_id']}")
            logger.info(f"{'-' * 80}")

            issue_result = self._evaluate_issue(issue, issue_number, workspace_path, session_context)

            session_results['issues'].append(issue_result)
            session_results['total_tokens'] += issue_result['metrics'].get('tokens_used', 0)

            if issue_result['degraded']:
                logger.warning(f"Degradation detected at issue {issue_number}")
                logger.warning(f"Signal: {issue_result['degradation_signal']}")

                session_results['degraded'] = True
                session_results['issues_completed'] = issue_number - 1
                session_results['degradation_signal'] = issue_result['degradation_signal']
                break
            else:
                logger.info(f"Issue {issue_number} completed successfully")
                session_results['issues_completed'] = issue_number

                session_context.add_issue_result(issue=issue, patch=issue_result['patch'],
                                                 test_result=issue_result['test_results'])

        session_results['total_time'] = time.time() - session_start_time

        logger.info(f"\n{'-' * 80}")
        logger.info(f"Session {session_id} complete:")
        logger.info(f"  Issues completed: {session_results['issues_completed']} of {len(issues)}")
        logger.info(f"  Degraded: {session_results['degraded']}")
        logger.info(f"  Total tokens: {session_results['total_tokens']}")
        logger.info(f"  Total time: {session_results['total_time']:.2f}s")
        logger.info(f"{'-' * 80}\n")

        if not self.config.keep_workspaces:
            self.repo_manager.cleanup(workspace_path, remove_workspace=True)

        return session_results

    def _load_strategy(self) -> Strategy:
        """
        Load strategy from config.

        Returns:
            Strategy
        """
        strategy_class_path = self.config.strategy_class

        if not strategy_class_path:
            raise ValueError("No strategy class specified in config")

        logger.info(f"Loading strategy: {strategy_class_path}")

        module_path, class_name = strategy_class_path.rsplit('.', 1)

        module = importlib.import_module(module_path)

        strategy_class = getattr(module, class_name)

        strategy = strategy_class(self.config.strategy_config)

        logger.info(f"Strategy loaded: {strategy}")

        return strategy

    def _evaluate_issue(self, issue: Dict[str, Any], issue_number: int, workspace_path: Path,
                        session_context: SessionContext) -> Dict[str, Any]:
        """
        Evaluate a single issue within a session.

        Args:
            issue: Issue data
            issue_number: Issue number (1-indexed)
            workspace_path: Path to workspace
            session_context: Current session context

        Returns:
            Issue result dictionary
        """
        issue_start_time = time.time()

        logger.info("   Generating patch...")
        try:
            patch_result = self.strategy.generate_patch(issue=issue, codebase_path=workspace_path,
                                                        session_context=session_context)
            patch = patch_result['patch']
            metadata = patch_result['metadata']
        except Exception as err:
            logger.error(f" Patch generation failed: {err}")
            return self._create_error_result(issue, issue_number, f"Patch generation error: {err}")

        logger.info(f"  Patch generated ({metadata.get('tokens_used', 0)} tokens)")

        # Apply patch to repository
        logger.info("   Applying patch...")
        apply_result = self.repo_manager.apply_patch(patch=patch, issue_id=issue['instance_id'],
                                                     workspace_path=workspace_path)

        if apply_result['applied']:
            logger.info(f"  Patch applied successfully")
        else:
            logger.error(f" Patch application failed: {apply_result['error']}")

        #  Run tests
        logger.info("   Running tests...")
        test_results = self.test_executor.run_tests(issue=issue, workspace_path=workspace_path,
                                                    previous_issues=session_context.issues_completed)

        if test_results['all_passed']:
            logger.info(f"  All tests passed")
        else:
            logger.warning(f"   Some tests failed")

        # Check constraints
        logger.info("   Checking constraints...")
        constraint_violations = self.constraint_manager.check_all(patch=patch, context={'issue': issue})

        if constraint_violations:
            logger.warning(f"   Found {len(constraint_violations)} constraint violation(s)")
        else:
            logger.info(f"  No constraint violations")

        # Check for degradation
        logger.info("   Checking for degradation...")
        degradation = self.degradation_detector.check_degradation(issue_number=issue_number, patch=patch,
                                                                  patch_applied=apply_result['applied'],
                                                                  test_results=test_results,
                                                                  constraint_violations=constraint_violations,
                                                                  session_context={
                                                                      'previous_patches': session_context.patches_generated,
                                                                      'previous_issues': session_context.issues_completed})

        if degradation['degraded']:
            logger.warning(f"   Degradation detected: {degradation['signal']}")
        else:
            logger.info(f"  No degradation detected")

        issue_result = {
            'issue_number': issue_number,
            'instance_id': issue['instance_id'],
            'patch': patch,
            'patch_applied': apply_result['applied'],
            'test_results': test_results,
            'constraint_violations': constraint_violations,
            'degraded': degradation['degraded'],
            'degradation_signal': degradation.get('signal'),
            'degradation_details': degradation.get('details'),
            'metrics': {
                **metadata,
                'time_elapsed': time.time() - issue_start_time
            }
        }

        return issue_result

    def _create_error_result(self, issue: Dict[str, Any], issue_number: int, error_message: str) -> Dict[str, Any]:
        """
        Create error result when issue evaluation fails.
        Args:
            issue: Issue data
            issue_number: Issue number
            error_message: Error description
        Returns:
            Error result dictionary
        """

        return {
            'issue_number': issue_number,
            'instance_id': issue['instance_id'],
            'patch': '',
            'patch_applied': False,
            'test_results': {'all_passed': False},
            'constraint_violations': [],
            'degraded': True,
            'degradation_signal': 'fatal_error',
            'degradation_details': error_message,
            'metrics': {
                'tokens_used': 0,
                'time_elapsed': 0.0
            }
        }
