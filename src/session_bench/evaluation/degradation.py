import importlib
from typing import Dict, Any, Optional, List, Callable
import logging

logger = logging.getLogger(__name__)


class DegradationDetector:
    """
    Detects context degradation across multiple signals.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.degradation_history = []
        self.default_compaction_keywords = [
            'compact context',
            'compacting context',
            'truncating context',
            'truncated context',
            'context window full',
            'context limit reached',
            'reducing context',
            'context too large',
            'cannot fit in context',
            'exceeded context',
            'summarizing context',
            'context length exceeded',
            'token limit',
            'memory full'
        ]
        self.compaction_keywords = self.config.get(
            'compaction_keywords',
            self.default_compaction_keywords
        )
        self.case_sensitive = self.config.get('case_sensitive', False)

        self.custom_checkers: List[Callable] = []
        self._load_custom_checkers()

    def _load_custom_checkers(self):
        """
        Load custom degradation checker functions from config.

        Config format:
            {
                'custom_checkers': [
                    {'module': 'my_module.checks', 'function': 'check_custom_check'},
                    {'module': 'my_module.checks', 'function': 'check_custom_check_1'}
                ]
            }
        """
        custom_configs = self.config.get('custom_checkers', [])

        for checker_config in custom_configs:
            module_path = checker_config.get('module')
            function_name = checker_config.get('function')

            if not module_path or not function_name:
                logger.warning(f"Custom checker missing 'module' or 'function' field, skipping")
                continue

            try:
                module = importlib.import_module(module_path)
                checker_func = getattr(module, function_name)

                if not callable(checker_func):
                    logger.error(f"Custom checker {module_path}.{function_name} is not callable")
                    continue

                self.custom_checkers.append(checker_func)
                logger.info(f"Loaded custom degradation checker: {module_path}.{function_name}")

            except Exception as err:
                logger.error(
                    f"Failed to load custom checker {module_path}.{function_name}: {err}")




    def check_degradation(self, issue_number: int, patch: str, patch_applied: bool, test_results: Dict[str, Any], constraint_violations: List[str],
                            session_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Check all degradation signals for one issue.
        """

        if not session_context:
            session_context = {}

        # PATCH FAILED
        signal = self._check_patch_application(patch_applied)
        if signal:
            return self._create_result(True, issue_number, 'patch_application_failure', signal)

        # CONSTRAINT VIOLATIONS
        signal = self._check_constraints(constraint_violations)
        if signal:
            return self._create_result(True, issue_number, 'architectural_violation', signal)

        # TEST FAILURES
        signal = self._check_test_failures(test_results)
        if signal:
            return self._create_result(True, issue_number, signal['type'], signal['details'])

        # CHECK FOR COMPACTION MSG
        signal = self._check_explicit_compaction(patch)
        if signal:
            return self._create_result(True, issue_number, 'explicit_compaction', signal)

        for custom_checker in self.custom_checkers:
            try:
                checker_context = {
                    'issue_number': issue_number,
                    'test_results': test_results,
                    'constraint_violations': constraint_violations,
                    **session_context
                }

                signal = custom_checker(patch, checker_context)

                if signal:
                    logger.warning(f"Custom checker {custom_checker.__name__} detected degradation"
                    )
                    return self._create_result(True, issue_number,'custom_degradation', signal)

            except Exception as err:
                logger.error(f"Custom checker {custom_checker.__name__} failed: {err}")


        return self._create_result(False, issue_number, None, None)



    def _create_result(self, degraded: bool, issue_number: int, signal: Optional[str], details: Optional[str]) -> Dict[str, Any]:
        """
        Creates degradation result.
        """

        result = {
            'degraded': degraded,
            'issue_number': issue_number,
            'signal': signal,
            'details': details
        }

        if degraded:
            logger.warning(
                f"Degradation detected at issue {issue_number}: "
                f"{signal} - {details}"
            )
            self.degradation_history.append(result)
        else:
            logger.info(f"No degradation detected at issue {issue_number}")

        return result

    def _check_patch_application(self, patch_applied: bool) -> Optional[str]:
        """
        Check if patch failed.
        """

        if not patch_applied:
            return "Generated patch failed to apply (likely due to conflict). Potential degradation detected."

        return None


    def _check_constraints(self, violations: List[str]) -> Optional[str]:
        """
        Check if architectural constraints were violated.
        """

        if violations:
            violation_summary = '\n'.join(f" - {v}" for v in violations)

            return (f"Generated code violates : {len(violations)} constraint(s).\n"
                    f"Violation summary : {violation_summary}")

        return None

    def _check_test_failures(self, test_results: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """
        Check for test failures.
        """

        if test_results.get('all_passed', True):
            return None

        regression = test_results.get('regression_tests', {})
        if regression.get('failed', 0) > 0:
            failed_count = regression['failed']
            return {
                'type': 'cross_issue_regression',
                'details': (
                    f"Current issue broke {failed_count} test(s) from previous issues. "
                )
            }

        sampled = test_results.get('sampled_tests', {})
        if sampled.get('failed', 0) > 0:
            failed_count = sampled['failed']
            return {
                'type': 'architectural_regression',
                'details': (
                    f"Current issue broke {failed_count} sample (unrelated) test(s). "
                )
            }

        issue_tests = test_results.get('issue_tests', {})
        if issue_tests.get('failed', 0) > 0:
            failed_count = issue_tests['failed']
            return {
                'type': 'test_failure',
                'details': (
                    f"Failed to pass {failed_count} issue-specific test(s). "
                )
            }

        return  None

    def _check_explicit_compaction(self, patch: str) -> Optional[str]:
        """
        Check if model explicity indicates context compaction.
        """

        search_text = patch if self.case_sensitive else patch.lower()

        for keyword in self.compaction_keywords:
            search_keyword = keyword if self.case_sensitive else keyword.lower()

            if search_keyword in search_text:
                logger.warning(f"Detected explicit compaction mention: '{keyword}'")
                return (
                    f"Model explicitly mentioned context issues: '{keyword}'. "
                )

        return None

    def get_degradation_history(self) -> List[Dict[str, Any]]:
        """
        Get degradation history.
        """

        return  self.degradation_history.copy()

    def reset(self):
        """
        Reset degradation history.
        """
        self.degradation_history = []
