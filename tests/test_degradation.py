import pytest
from session_bench.evaluation.degradation import DegradationDetector


def test_degradation_detector_init():
    """
    Test degradation detector initialization.
    """
    detector = DegradationDetector()

    assert detector.degradation_history == []
    assert len(detector.default_compaction_keywords) > 0
    assert detector.case_sensitive is False


def test_patch_application_failure():
    """
    Test detection of patch application failure.
    """
    detector = DegradationDetector()

    result = detector.check_degradation(
        issue_number=2,
        patch="some patch",
        patch_applied=False,
        test_results={'all_passed': True},
        constraint_violations=[]
    )

    assert result['degraded'] is True
    assert result['signal'] == 'patch_application_failure'
    assert result['issue_number'] == 2
    assert 'conflict' in result['details'].lower()


def test_constraint_violations():
    """
    Test detection of constraint violations.
    """
    detector = DegradationDetector()

    violations = [
        "ORM Violation: Raw SQL detected",
        "Naming Violation: Bad method name"
    ]

    result = detector.check_degradation(
        issue_number=3,
        patch="some patch",
        patch_applied=True,
        test_results={'all_passed': True},
        constraint_violations=violations
    )

    assert result['degraded'] is True
    assert result['signal'] == 'architectural_violation'
    assert '2' in result['details']


def test_cross_issue_regression():
    """
    Test detection of cross-issue regression.
    """
    detector = DegradationDetector()

    test_results = {
        'all_passed': False,
        'issue_tests': {'passed': 5, 'failed': 0},
        'regression_tests': {'passed': 2, 'failed': 3},
        'sampled_tests': {'passed': 20, 'failed': 0}
    }

    result = detector.check_degradation(
        issue_number=3,
        patch="some patch",
        patch_applied=True,
        test_results=test_results,
        constraint_violations=[]
    )

    assert result['degraded'] is True
    assert result['signal'] == 'cross_issue_regression'
    assert 'previous issues' in result['details'].lower()


def test_issue_test_failure():
    """
    Test detection of issue-specific test failure.
    """
    detector = DegradationDetector()

    test_results = {
        'all_passed': False,
        'issue_tests': {'passed': 2, 'failed': 3},
        'regression_tests': {'passed': 5, 'failed': 0},
        'sampled_tests': {'passed': 20, 'failed': 0}
    }

    result = detector.check_degradation(
        issue_number=1,
        patch="some patch",
        patch_applied=True,
        test_results=test_results,
        constraint_violations=[]
    )

    assert result['degraded'] is True
    assert result['signal'] == 'test_failure'


def test_sampled_test_failure():
    """
    Test detection of sampled (unrelated) test failures.
    """
    detector = DegradationDetector()

    test_results = {
        'all_passed': False,
        'issue_tests': {'passed': 5, 'failed': 0},
        'regression_tests': {'passed': 5, 'failed': 0},
        'sampled_tests': {'passed': 15, 'failed': 5}
    }

    result = detector.check_degradation(
        issue_number=4,
        patch="some patch",
        patch_applied=True,
        test_results=test_results,
        constraint_violations=[]
    )

    assert result['degraded'] is True
    assert result['signal'] == 'architectural_regression'
    assert 'unrelated' in result['details'].lower()


def test_explicit_compaction():
    """
    Test detection of explicit context compaction mention.
    """
    detector = DegradationDetector()

    patch = """
    diff --git a/file.py b/file.py
    # Note: Had to compact context due to context window being full
    +def new_function():
    +    pass
    """

    result = detector.check_degradation(
        issue_number=5,
        patch=patch,
        patch_applied=True,
        test_results={'all_passed': True},
        constraint_violations=[]
    )

    assert result['degraded'] is True
    assert result['signal'] == 'explicit_compaction'
    assert 'context' in result['details'].lower()


def test_no_degradation():
    """
    Test when no degradation is detected.
    """
    detector = DegradationDetector()

    result = detector.check_degradation(
        issue_number=2,
        patch="clean patch",
        patch_applied=True,
        test_results={'all_passed': True},
        constraint_violations=[]
    )

    assert result['degraded'] is False
    assert result['signal'] is None
    assert result['details'] is None



def test_degradation_priority():
    """
    Test that degradation signals are checked in priority order.
    """
    detector = DegradationDetector()

    result = detector.check_degradation(
        issue_number=3,
        patch="patch with context window full",
        patch_applied=False,
        test_results={'all_passed': False},
        constraint_violations=['Some violation']
    )

    assert result['signal'] == 'patch_application_failure'


def test_degradation_history():
    """
    Test degradation history tracking.
    """
    detector = DegradationDetector()

    detector.check_degradation(
        issue_number=1,
        patch="clean",
        patch_applied=True,
        test_results={'all_passed': True},
        constraint_violations=[]
    )

    assert len(detector.get_degradation_history()) == 0

    detector.check_degradation(
        issue_number=2,
        patch="bad",
        patch_applied=False,
        test_results={'all_passed': True},
        constraint_violations=[]
    )

    history = detector.get_degradation_history()
    assert len(history) == 1
    assert history[0]['issue_number'] == 2
    assert history[0]['signal'] == 'patch_application_failure'


def test_degradation_reset():
    """
    Test resetting degradation history.
    """
    detector = DegradationDetector()

    detector.check_degradation(
        issue_number=2,
        patch="bad",
        patch_applied=False,
        test_results={'all_passed': True},
        constraint_violations=[]
    )

    assert len(detector.get_degradation_history()) == 1

    detector.reset()

    assert len(detector.get_degradation_history()) == 0


def test_custom_compaction_keywords():
    """
    Test using custom compaction keywords.
    """
    config = {
        'compaction_keywords': ['my_model_says_full', 'custom_phrase']
    }

    detector = DegradationDetector(config)

    patch = "Some code with my_model_says_full in it"

    result = detector.check_degradation(
        issue_number=3,
        patch=patch,
        patch_applied=True,
        test_results={'all_passed': True},
        constraint_violations=[]
    )

    assert result['degraded'] is True
    assert result['signal'] == 'explicit_compaction'


def test_case_sensitive_keywords():
    """
    Test case-sensitive keyword matching.
    """
    config = {
        'compaction_keywords': ['CONTEXT FULL'],
        'case_sensitive': True
    }

    detector = DegradationDetector(config)

    patch1 = "context full"
    result1 = detector.check_degradation(
        issue_number=1,
        patch=patch1,
        patch_applied=True,
        test_results={'all_passed': True},
        constraint_violations=[]
    )
    assert result1['degraded'] is False

    patch2 = "CONTEXT FULL"
    result2 = detector.check_degradation(
        issue_number=2,
        patch=patch2,
        patch_applied=True,
        test_results={'all_passed': True},
        constraint_violations=[]
    )
    assert result2['degraded'] is True


def test_disabled_compaction_check():
    """
    Test disabling compaction check with empty keyword list.
    """
    config = {
        'compaction_keywords': []
    }

    detector = DegradationDetector(config)

    patch = "compact context truncating context token limit"

    result = detector.check_degradation(
        issue_number=1,
        patch=patch,
        patch_applied=True,
        test_results={'all_passed': True},
        constraint_violations=[]
    )

    assert result['degraded'] is False


def test_custom_checker_simple():
    """
    Test loading and using a simple custom checker.
    """

    def check_large_patch(patch, context):
        if len(patch) > 100:
            return "Patch is too large (complexity explosion)"
        return None


    detector = DegradationDetector()
    detector.custom_checkers = [check_large_patch]

    result = detector.check_degradation(
        issue_number=1,
        patch="small patch",
        patch_applied=True,
        test_results={'all_passed': True},
        constraint_violations=[]
    )

    assert result['degraded'] is False

    large_patch = "x" * 150
    result = detector.check_degradation(
        issue_number=2,
        patch=large_patch,
        patch_applied=True,
        test_results={'all_passed': True},
        constraint_violations=[]
    )

    assert result['degraded'] is True
    assert result['signal'] == 'custom_degradation'
    assert 'too large' in result['details']


def test_custom_checker_with_context():
    """
    Test custom checker that uses session context.
    """

    def check_code_duplication(patch, context):
        previous_patches = context.get('previous_patches', [])
        for prev in previous_patches:
            if patch == prev:
                return "Code duplication detected - same patch as before"
        return None

    detector = DegradationDetector()
    detector.custom_checkers = [check_code_duplication]

    result = detector.check_degradation(
        issue_number=1,
        patch="patch A",
        patch_applied=True,
        test_results={'all_passed': True},
        constraint_violations=[],
        session_context={'previous_patches': []}
    )

    assert result['degraded'] is False

    result = detector.check_degradation(
        issue_number=2,
        patch="patch A",
        patch_applied=True,
        test_results={'all_passed': True},
        constraint_violations=[],
        session_context={'previous_patches': ['patch A']}
    )

    assert result['degraded'] is True
    assert result['signal'] == 'custom_degradation'
    assert 'duplication' in result['details'].lower()


def test_custom_checker_exception_handling():
    """
    Test that exceptions in custom checkers don't crash the detector.
    """

    def buggy_checker(patch, context):
        raise ValueError("Intentional error for testing")

    def good_checker(patch, context):
        if 'bad' in patch:
            return "Found bad keyword"
        return None

    detector = DegradationDetector()
    detector.custom_checkers = [buggy_checker, good_checker]

    result = detector.check_degradation(
        issue_number=1,
        patch="contains bad keyword",
        patch_applied=True,
        test_results={'all_passed': True},
        constraint_violations=[]
    )

    assert result['degraded'] is True
    assert result['signal'] == 'custom_degradation'


def test_multiple_custom_checkers():
    """
    Test using multiple custom checkers.
    """

    def check_complexity(patch, context):
        if patch.count('\n') > 50:
            return "Too many lines"
        return None

    def check_keywords(patch, context):
        if 'forbidden' in patch:
            return "Forbidden keyword detected"
        return None

    detector = DegradationDetector()
    detector.custom_checkers = [check_complexity, check_keywords]

    result1 = detector.check_degradation(
        issue_number=1,
        patch="\n" * 60,
        patch_applied=True,
        test_results={'all_passed': True},
        constraint_violations=[]
    )

    assert result1['degraded'] is True
    assert 'Too many lines' in result1['details']

    result2 = detector.check_degradation(
        issue_number=2,
        patch="code with forbidden keyword",
        patch_applied=True,
        test_results={'all_passed': True},
        constraint_violations=[]
    )

    assert result2['degraded'] is True
    assert 'Forbidden' in result2['details']


def test_custom_checker_priority():
    """
    Test that built-in checks have priority over custom checks.
    """

    def custom_checker(patch, context):
        return "Custom degradation"

    detector = DegradationDetector()
    detector.custom_checkers = [custom_checker]

    result = detector.check_degradation(
        issue_number=1,
        patch="would trigger custom",
        patch_applied=False,
        test_results={'all_passed': True},
        constraint_violations=[]
    )

    assert result['signal'] == 'patch_application_failure'
    assert result['signal'] != 'custom_degradation'


def test_empty_test_results():
    """
    Test handling of minimal test results.
    """
    detector = DegradationDetector()

    result = detector.check_degradation(
        issue_number=1,
        patch="some patch",
        patch_applied=True,
        test_results={},
        constraint_violations=[]
    )

    assert result['degraded'] is False


def test_none_session_context():
    """
    Test handling of None session context.
    """
    detector = DegradationDetector()

    result = detector.check_degradation(
        issue_number=1,
        patch="some patch",
        patch_applied=True,
        test_results={'all_passed': True},
        constraint_violations=[],
        session_context=None
    )

    assert result['degraded'] is False


def test_empty_patch():
    """
    Test handling of empty patch.
    """
    detector = DegradationDetector()

    result = detector.check_degradation(
        issue_number=1,
        patch="",
        patch_applied=True,
        test_results={'all_passed': True},
        constraint_violations=[]
    )
    assert result['degraded'] is False