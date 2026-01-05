import pytest
from pathlib import Path
from session_bench.evaluation.testing import TestExecutor


def test_test_executor_init():
    """
    Test test executor initialization.
    """
    config = {
        'run_issue_tests': True,
        'run_regression_tests': True,
        'run_random_sample': False,
        'test_timeout': 300
    }

    executor = TestExecutor(config)

    assert executor.enable_issue_tests is True
    assert executor.enable_regression_tests is True
    assert executor.enable_random_sample is False
    assert executor.test_timeout == 300


def test_run_issue_tests_only():
    """
    Test running only issue-specific tests.
    """
    config = {
        'run_issue_tests': True,
        'run_regression_tests': False,
        'run_random_sample': False
    }

    executor = TestExecutor(config)

    issue = {
        'instance_id': 'django__django-12345',
        'FAIL_TO_PASS': ['test_models.TestModel.test_save'],
        'PASS_TO_PASS': ['test_models.TestModel.test_load']
    }

    results = executor.run_tests(
        issue=issue,
        workspace_path=Path('/tmp/test'),
        previous_issues=[]
    )

    assert 'issue_tests' in results
    assert results['issue_tests']['total'] == 2
    assert 'regression_tests' not in results
    assert 'sampled_tests' not in results


def test_run_with_regression():
    """
    Test running issue + regression tests.
    """
    config = {
        'run_issue_tests': True,
        'run_regression_tests': True,
        'run_random_sample': False
    }

    executor = TestExecutor(config)

    # Current issue
    issue = {
        'instance_id': 'django__django-12345',
        'FAIL_TO_PASS': ['test_new.TestNew.test_feature'],
        'PASS_TO_PASS': []
    }

    # Previous issues
    previous_issues = [
        {
            'instance_id': 'django__django-12340',
            'FAIL_TO_PASS': ['test_old.TestOld.test_old_feature'],
            'PASS_TO_PASS': []
        }
    ]

    results = executor.run_tests(
        issue=issue,
        workspace_path=Path('/tmp/test'),
        previous_issues=previous_issues
    )

    assert 'issue_tests' in results
    assert 'regression_tests' in results
    assert results['regression_tests']['total'] == 1


def test_all_passed_flag():
    """
    Test that all_passed flag is set correctly.
    """
    config = {
        'run_issue_tests': True,
        'run_regression_tests': False
    }

    executor = TestExecutor(config)

    issue = {
        'instance_id': 'django__django-12345',
        'FAIL_TO_PASS': ['test_1', 'test_2'],
        'PASS_TO_PASS': []
    }

    results = executor.run_tests(
        issue=issue,
        workspace_path=Path('/tmp/test')
    )

    # Mock always passes
    assert results['all_passed'] is True


def test_empty_test_lists():
    """
    Test handling of issues with no tests.
    """
    config = {
        'run_issue_tests': True
    }

    executor = TestExecutor(config)

    issue = {
        'instance_id': 'django__django-12345',
        'FAIL_TO_PASS': [],
        'PASS_TO_PASS': []
    }

    results = executor.run_tests(
        issue=issue,
        workspace_path=Path('/tmp/test')
    )

    assert results['issue_tests']['total'] == 0


def test_config_defaults():
    """
    Test that config uses sensible defaults.
    """
    config = {}

    executor = TestExecutor(config)

    # test defaults
    assert executor.enable_issue_tests is True  # Should default to True
    assert executor.enable_regression_tests is True  # Should default to True
    assert executor.enable_random_sample is False  # Should default to False
    assert executor.test_timeout == 300  # Should default to 300


def test_tier_selection():
    """
    Test selective test execution.
    """
    config = {
        'run_issue_tests': False,
        'run_regression_tests': False,
        'run_random_sample': True,
        'random_sample_size': 10
    }

    executor = TestExecutor(config)

    assert executor.enable_issue_tests is False
    assert executor.enable_regression_tests is False
    assert executor.enable_random_sample is True
    assert executor.random_sample_size == 10


def test_multiple_previous_issues():
    """
    Test regression testing with multiple previous issues.
    """
    config = {
        'run_issue_tests': True,
        'run_regression_tests': True
    }

    executor = TestExecutor(config)

    issue = {
        'instance_id': 'django__django-12345',
        'FAIL_TO_PASS': ['test_current.TestCurrent.test_new'],
        'PASS_TO_PASS': []
    }

    previous_issues = [
        {
            'instance_id': 'django__django-12340',
            'FAIL_TO_PASS': ['test_1', 'test_2'],
            'PASS_TO_PASS': []
        },
        {
            'instance_id': 'django__django-12341',
            'FAIL_TO_PASS': ['test_3', 'test_4', 'test_5'],
            'PASS_TO_PASS': []
        }
    ]

    results = executor.run_tests(
        issue=issue,
        workspace_path=Path('/tmp/test'),
        previous_issues=previous_issues
    )

    assert results['issue_tests']['total'] == 1
    assert results['regression_tests']['total'] == 5


def test_no_previous_issues():
    """
    Test that regression tests are skipped when no previous issues.
    """
    config = {
        'run_issue_tests': True,
        'run_regression_tests': True
    }

    executor = TestExecutor(config)

    issue = {
        'instance_id': 'django__django-12345',
        'FAIL_TO_PASS': ['test_1'],
        'PASS_TO_PASS': []
    }

    results = executor.run_tests(
        issue=issue,
        workspace_path=Path('/tmp/test'),
        previous_issues=[]
    )

    assert 'issue_tests' in results
    assert 'regression_tests' not in results