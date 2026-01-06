import pytest
import logging
from session_bench.evaluation.testing import TestExecutor
from session_bench.repository.manager import RepositoryManager


logger = logging.getLogger(__name__)


@pytest.mark.slow
@pytest.mark.integration
def test_real_django_issue(tmp_path):
    """
    Test with an actual Django issue from SWE-bench.

    - Clones real Django repository
    - Installs dependencies automatically
    - Runs actual Django tests
    - Returns real pass/fail results

    """
    issue = {
        "instance_id": "django__django-11039",
        "repo": "django/django",
        "base_commit": "419a78300f7cd27611196e1e464d50fd0385ff27",
        "problem_statement": "sqlmigrate wraps its output SQL in BEGIN/COMMIT even if the database doesn't support transactional DDL",
        "version": "3.0",
        "FAIL_TO_PASS": [
            "migrations.test_commands.MigrateTests.test_sqlmigrate_no_transactional_ddl"
        ],
        "PASS_TO_PASS": [
            "migrations.test_commands.MigrateTests.test_sqlmigrate_forwards"
        ],
        "test_cmd": "cd tests && python runtests.py --parallel 1 {test}"
    }

    logger.info("-" * 80)
    logger.info(f"Testing real SWE-bench issue: {issue['instance_id']}")
    logger.info("-" * 80)

    logger.info("Setting up Django repository...")
    repo_manager = RepositoryManager(tmp_path / 'workspaces')
    workspace = repo_manager.setup_repository(
        session_id='swebench_test',
        repo_url='https://github.com/django/django.git',
        base_commit=issue['base_commit']
    )
    logger.info(f" Repository ready: {workspace}")

    logger.info("Initializing test executor...")
    config = {
        'run_issue_tests': True,
        'run_regression_tests': False,
        'run_random_sample': False,
        'test_timeout': 300
    }

    executor = TestExecutor(config)
    logger.info("Test executor ready")

    logger.info("Running tests...")
    results = executor.run_tests(
        issue=issue,
        workspace_path=workspace,
        previous_issues=[]
    )

    logger.info("-" * 80)
    logger.info("RESULTS:")
    logger.info("-" * 80)
    logger.info(f"Total: {results['issue_tests']['total']}")
    logger.info(f"Passed: {results['issue_tests']['passed']}")
    logger.info(f"Failed: {results['issue_tests']['failed']}")

    for test in results['issue_tests']['tests']:
        logger.info(f" {test['name']}: {test['status']}")

    logger.info("Cleaning up...")
    repo_manager.cleanup(workspace, remove_workspace=True)

    assert results['issue_tests']['total'] > 0, "Should have run tests"
    assert results['issue_tests']['passed'] > 0, "At least PASS_TO_PASS test should pass"

    logger.info("-" * 80)
    logger.info("Integration test PASSED!")
    logger.info("-" * 80)