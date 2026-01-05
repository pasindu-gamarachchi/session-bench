import pytest
from session_bench.core.config import ExperimentConfig
from session_bench.core.strategy import Strategy
from session_bench.session.evaluator import SessionEvaluator


class DummyStrategy(Strategy):
    """
    Dummy strategy for testing.
    """

    def __init__(self, config):
        super().__init__(config)
        self.call_count = 0

    def generate_patch(self, issue, codebase_path, session_context):
        self.call_count += 1

        patch = f"""diff --git a/test_{self.call_count}.py b/test_{self.call_count}.py
new file mode 100644
--- /dev/null
+++ b/test_{self.call_count}.py
@@ -0,0 +1,2 @@
+def test_function_{self.call_count}():
+    pass
"""

        return {
            'patch': patch,
            'metadata': {
                'tokens_used': 100,
                'time_elapsed': 1.0,
                'model_calls': 1
            }
        }


@pytest.fixture
def temp_config(tmp_path):
    """
    Create a temporary config for testing.
    """
    config_dict = {
        'experiment': {
            'name': 'test_experiment',
            'description': 'Test',
            'random_seed': 42
        },
        'dataset': {
            'sessions_file': 'data/test.json',
            'session_ids': [1]
        },
        'strategy': {
            'class': 'tests.test_session_evaluator.DummyStrategy',
            'config': {'test': True}
        },
        'testing': {
            'run_issue_tests': True,
            'run_regression_tests': False,
            'run_random_sample': False
        },
        'constraints': {
            'builtin': {
                'check_orm_usage': False,
                'check_view_patterns': False,
                'check_naming_convention': False
            }
        },
        'workspace': {
            'base_dir': str(tmp_path / 'workspaces'),
            'keep_workspaces': False
        },
        'output': {
            'results_dir': str(tmp_path / 'results'),
            'log_level': 'INFO'
        }
    }

    config = ExperimentConfig(
        name='test_experiment',
        description='Test',
        strategy_class='tests.test_session_evaluator.DummyStrategy',
        strategy_config={'test': True},
        session_ids=[1],
        workspace_dir=tmp_path / 'workspaces',
        results_dir=tmp_path / 'results',
        run_issue_tests=True,
        run_regression_tests=False,
        run_random_sample=False,
        check_orm_usage=False,
        check_view_patterns=False,
        check_naming_convention=False,
        extra_config={'constraints': {'builtin': {}}, 'degradation': {}}
    )

    return config


def test_session_evaluator_init(temp_config):
    """
    Test session evaluator initialization.
    """
    evaluator = SessionEvaluator(temp_config)

    assert evaluator.config == temp_config
    assert evaluator.repo_manager is not None
    assert evaluator.constraint_manager is not None
    assert evaluator.degradation_detector is not None
    assert evaluator.test_executor is not None
    assert evaluator.strategy is None


def test_load_strategy(temp_config):
    """
    Test loading strategy dynamically.
    """
    evaluator = SessionEvaluator(temp_config)

    strategy = evaluator._load_strategy()

    assert strategy is not None
    assert isinstance(strategy, DummyStrategy)


def test_create_error_result(temp_config):
    """
    Test creating error result.
    """
    evaluator = SessionEvaluator(temp_config)

    issue = {
        'instance_id': 'test-123',
        'problem_statement': 'Test issue'
    }

    error_result = evaluator._create_error_result(
        issue=issue,
        issue_number=1,
        error_message='Test error'
    )

    assert error_result['issue_number'] == 1
    assert error_result['instance_id'] == 'test-123'
    assert error_result['degraded'] is True
    assert error_result['degradation_signal'] == 'fatal_error'
    assert 'Test error' in error_result['degradation_details']


@pytest.mark.slow
def test_run_session_simple(temp_config):
    """
    Test running a simple session with mock data.
    """
    evaluator = SessionEvaluator(temp_config)
    session = {
        'session_id': 1,
        'repo_url': 'https://github.com/octocat/Hello-World.git',
        'base_commit': '7fd1a60b01f91b314f59955a4e4d4e80d8edf11d',
        'issues': [
            {
                'instance_id': 'test-001',
                'problem_statement': 'Add a feature',
                'FAIL_TO_PASS': ['test_feature'],
                'PASS_TO_PASS': []
            }
        ]
    }

    results = evaluator.run_session(session)

    assert results['session_id'] == 1
    assert results['strategy'] == 'tests.test_session_evaluator.DummyStrategy'
    assert 'degraded' in results
    assert 'issues_completed' in results
    assert len(results['issues']) == 1

    issue_result = results['issues'][0]
    assert issue_result['issue_number'] == 1
    assert issue_result['instance_id'] == 'test-001'
    assert 'patch' in issue_result
    assert 'test_results' in issue_result


@pytest.mark.slow
def test_run_session_multiple_issues(temp_config):
    """
    Test running a session with multiple issues.
    """
    evaluator = SessionEvaluator(temp_config)

    session = {
        'session_id': 2,
        'repo_url': 'https://github.com/octocat/Hello-World.git',
        'base_commit': '7fd1a60b01f91b314f59955a4e4d4e80d8edf11d',
        'issues': [
            {
                'instance_id': 'test-001',
                'problem_statement': 'Issue 1',
                'FAIL_TO_PASS': ['test_1'],
                'PASS_TO_PASS': [],
                'test_cmd': 'echo "pass"'  # ← Add this
            },
            {
                'instance_id': 'test-002',
                'problem_statement': 'Issue 2',
                'FAIL_TO_PASS': ['test_2'],
                'PASS_TO_PASS': [],
                'test_cmd': 'echo "pass"'  # ← Add this
            },
            {
                'instance_id': 'test-003',
                'problem_statement': 'Issue 3',
                'FAIL_TO_PASS': ['test_3'],
                'PASS_TO_PASS': [],
                'test_cmd': 'echo "pass"'  # ← Add this
            }
        ]
    }

    results = evaluator.run_session(session)

    assert len(results['issues']) == 3
    assert results['issues_completed'] == 3
    assert results['degraded'] is False


def test_evaluate_issue_structure(temp_config):
    """
    Test that issue evaluation returns correct structure.
    """
    evaluator = SessionEvaluator(temp_config)
    evaluator.strategy = evaluator._load_strategy()

    issue = {
        'instance_id': 'test-123',
        'problem_statement': 'Test'
    }

    error_result = evaluator._create_error_result(issue, 1, 'Test error')

    required_fields = [
        'issue_number',
        'instance_id',
        'patch',
        'patch_applied',
        'test_results',
        'constraint_violations',
        'degraded',
        'degradation_signal',
        'degradation_details',
        'metrics'
    ]

    for field in required_fields:
        assert field in error_result


def test_session_result_structure(temp_config):
    """
    Test that session results have correct structure.
    """
    evaluator = SessionEvaluator(temp_config)

    session_results = {
        'session_id': 1,
        'strategy': temp_config.strategy_class,
        'degraded': False,
        'issues_completed': 0,
        'degradation_signal': None,
        'issues': [],
        'total_tokens': 0,
        'total_time': 0.0
    }

    required_fields = [
        'session_id',
        'strategy',
        'degraded',
        'issues_completed',
        'degradation_signal',
        'issues',
        'total_tokens',
        'total_time'
    ]

    for field in required_fields:
        assert field in session_results


def test_session_context_accumulation(temp_config):
    """
    Test that session context accumulates across issues.
    """
    from session_bench.core.strategy import SessionContext

    context = SessionContext(constraints={'test': True})

    issue1 = {'instance_id': 'test-001'}
    patch1 = 'patch 1 content'
    test1 = {'passed': True}

    context.add_issue_result(issue1, patch1, test1)

    assert len(context.issues_completed) == 1
    assert len(context.patches_generated) == 1
    assert len(context.test_results) == 1

    issue2 = {'instance_id': 'test-002'}
    patch2 = 'patch 2 content'
    test2 = {'passed': True}

    context.add_issue_result(issue2, patch2, test2)

    assert len(context.issues_completed) == 2
    assert len(context.patches_generated) == 2
    assert len(context.test_results) == 2