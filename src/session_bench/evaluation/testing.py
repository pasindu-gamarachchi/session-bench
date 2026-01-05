from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class TestExecutor:
    """
    Executes tests sign SWE-bench test harness.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enable_issue_tests = config.get('run_issue_tests', True)
        self.enable_regression_tests = config.get('run_regression_tests', True)
        self.enable_random_sample = config.get('run_random_sample', False)
        self.random_sample_size = config.get('random_sample_size', 20)
        self.test_timeout = config.get('test_timeout', 300)

        logger.info(f"TestExecutor initialized: issue={self.enable_issue_tests}, "
                   f"regression={self.enable_regression_tests}, "
                   f"sample={self.enable_random_sample}")

    def run_tests(self, issue: Dict[str, Any], workspace_path: Path, previous_issues: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Run all configured test tiers for an issue.

        Args:
            issue: SWE-bench issue dictionary
            workspace_path: Path to workspace with applied patch
            previous_issues: List of previously completed issues

        Returns:
            {
                'all_passed': bool,
                'issue_tests': {
                    'passed': int,
                    'failed': int,
                    'total': int,
                    'tests': [{'name': str, 'status': str, 'output': str}]
                },
                'regression_tests': {...},  # If enabled
                'sampled_tests': {...}      # If enabled
            }
        """
        if previous_issues is None:
            previous_issues = []

        results = {}
        all_passed = True

        # Issue-specific tests
        if self.enable_issue_tests:
            logger.info(f"Running issue tests for {issue['instance_id']}")
            issue_results = self._run_issue_tests(issue, workspace_path)
            results['issue_tests'] = issue_results

            if issue_results['failed'] > 0:
                all_passed = False

        # Regression tests
        if self.enable_regression_tests and previous_issues:
            logger.info(f"Running regression tests ({len(previous_issues)} previous issues)")
            regression_results = self._run_regression_tests(previous_issues, workspace_path)
            results['regression_tests'] = regression_results

            if regression_results['failed'] > 0:
                all_passed = False

        # Random sample tests
        if self.enable_random_sample:
            logger.info(f"Running random sample ({self.random_sample_size} tests)")
            sample_results = self._run_sampled_tests(issue, workspace_path, self.random_sample_size)
            results['sampled_tests'] = sample_results

            if sample_results['failed'] > 0:
                all_passed = False

        results['all_passed'] = all_passed

        return results

    def _run_issue_tests(self, issue: Dict[str, Any], workspace_path: Path) -> Dict[str, Any]:
        """
        Run issue-specific tests
        These are the tests that should pass after the patch is applied.

        Args:
            issue: SWE-bench issue
            workspace_path: Path to workspace
        Returns:
            Test results dictionary
        """
        fail_to_pass = issue.get('FAIL_TO_PASS', [])
        pass_to_pass = issue.get('PASS_TO_PASS', [])

        all_tests = fail_to_pass + pass_to_pass

        if not all_tests:
            logger.warning(f"No tests specified for {issue['instance_id']}")
            return {
                'passed': 0,
                'failed': 0,
                'total': 0,
                'tests': []
            }

        logger.info(f"Running {len(all_tests)} issue tests "
                    f"(FAIL_TO_PASS: {len(fail_to_pass)}, PASS_TO_PASS: {len(pass_to_pass)})")

        test_results = self._execute_tests(all_tests, workspace_path, issue)

        return test_results

    def _run_regression_tests(self, previous_issues: List[Dict[str, Any]], workspace_path: Path) -> Dict[str, Any]:
        """
        Run tests from previously completed issues to check if current patch broke fixes from earlier issues.

        Args:
            previous_issues: List of completed issues
            workspace_path: Path to workspace

        Returns:
            Test results dictionary
        """
        all_regression_tests = []

        for prev_issue in previous_issues:
            fail_to_pass = prev_issue.get('FAIL_TO_PASS', [])
            all_regression_tests.extend(fail_to_pass)

        if not all_regression_tests:
            return {
                'passed': 0,
                'failed': 0,
                'total': 0,
                'tests': []
            }

        logger.info(f"Running {len(all_regression_tests)} regression tests")

        # Run tests (use first issue for context - doesn't really matter which)
        test_results = self._execute_tests(
            all_regression_tests,
            workspace_path,
            previous_issues[0] if previous_issues else {}
        )

        return test_results

    def _run_sampled_tests(self, issue: Dict[str, Any], workspace_path: Path, sample_size: int) -> Dict[str, Any]:
        """
        Run random sample of tests.

        Args:
            issue: Current issue (for context)
            workspace_path: Path to workspace
            sample_size: Number of tests to sample

        Returns:
            Test results dictionary
        """
        # TODO: Implement test discovery and random sampling
        logger.warning("Random test sampling not yet implemented")

        return {
            'passed': 0,
            'failed': 0,
            'total': 0,
            'tests': []
        }

    def _execute_tests(self, test_list: List[str], workspace_path: Path, issue: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a list of tests using SWE-bench harness.
        This is the core test execution logic that interfaces with SWE-bench.

        Args:
            test_list: List of test identifiers (e.g., 'test_module.TestClass.test_method')
            workspace_path: Path to workspace
            issue: Issue dictionary (for context)

        Returns:
            {
                'passed': int,
                'failed': int,
                'total': int,
                'tests': [
                    {
                        'name': str,
                        'status': 'passed'|'failed'|'error',
                        'output': str
                    }
                ]
            }
        """
        # TODO: Implement actual SWE-bench integration
        # For now, return mock results

        logger.info(f"Executing {len(test_list)} tests in {workspace_path}")

        # Mock implementation - will be replaced with real SWE-bench integration
        passed = 0
        failed = 0
        test_results = []

        for test_name in test_list:
            # Mock: assume all tests pass for now
            test_results.append({
                'name': test_name,
                'status': 'passed',
                'output': 'Test passed (mock)'
            })
            passed += 1

        return {
            'passed': passed,
            'failed': failed,
            'total': len(test_list),
            'tests': test_results
        }