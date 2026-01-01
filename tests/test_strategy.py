import pytest
from pathlib import Path
from session_bench.core.strategy import Strategy, SessionContext


class DummyStrategy(Strategy):

    def generate_patch(self, issue, codebase_path, session_context):
        """
        Return a dummy patch.
        """
        self._metrics['total_calls'] += 1
        self._metrics['total_tokens'] += 100

        return {
            'patch': 'diff --git a/test.py b/test.py\n+# test',
            'metadata': {
                'tokens_used': 100,
                'time_elapsed': 1.0,
                'model_calls': 1
            }
        }


def test_session_context():
    """
    Test SessionContext tracks issues correctly.
    """
    context = SessionContext(constraints={'check_orm': True})

    issue = {'instance_id': 'test-123', 'problem_statement': 'Fix bug'}
    patch = 'diff --git a/file.py b/file.py'
    test_result = {'passed': True}

    context.add_issue_result(issue, patch, test_result)

    assert len(context.issues_completed) == 1
    assert len(context.patches_generated) == 1
    assert context.issues_completed[0]['instance_id'] == 'test-123'


def test_strategy_interface():
    """
    Test strategy can be instantiated and used.
    """
    config = {'model': 'test-model'}
    strategy = DummyStrategy(config)

    issue = {'instance_id': 'test-123'}
    codebase_path = Path('/tmp')
    context = SessionContext()

    result = strategy.generate_patch(issue, codebase_path, context)

    assert 'patch' in result
    assert 'metadata' in result
    assert result['metadata']['tokens_used'] == 100


def test_strategy_metrics():
    """
    Test strategy tracks metrics.
    """
    strategy = DummyStrategy({})

    for i in range(3):
        strategy.generate_patch({}, Path('/tmp'), SessionContext())

    metrics = strategy.get_metrics()

    assert metrics['total_calls'] == 3
    assert metrics['total_tokens'] == 300

    strategy.reset_metrics()
    metrics = strategy.get_metrics()

    assert metrics['total_calls'] == 0
    assert metrics['total_tokens'] == 0


def test_extract_files_from_patch():
    """
    Test extracting file paths from patches.
    """
    patch = """diff --git a/django/db/models.py b/django/db/models.py
index 123..456
--- a/django/db/models.py
+++ b/django/db/models.py
@@ -10,3 +10,4 @@
+new line
diff --git a/tests/test_models.py b/tests/test_models.py
"""

    context = SessionContext()
    files = context._extract_files_from_patch(patch)

    assert 'django/db/models.py' in files
    assert 'tests/test_models.py' in files
    assert len(files) == 2