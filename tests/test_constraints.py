import pytest
from session_bench.evaluation.constraints import ConstraintManager, ConstraintChecker
from session_bench.evaluation.constraints.builtin import ORMConstraintChecker, ViewPatternChecker, NamingConventionChecker


def test_base_class_provides_extract_helper():
    """
    Test that base class provides _extract_added_lines helper.
    """

    class TestChecker(ConstraintChecker):
        def check(self, patch, context):
            return []

    checker = TestChecker()

    # Test the helper method is available
    patch = """diff --git a/file.py b/file.py
+added line 1
+added line 2
-removed line
 context line
"""

    added_lines = checker._extract_added_lines(patch)

    assert len(added_lines) == 2
    assert 'added line 1' in added_lines
    assert 'added line 2' in added_lines
    assert 'removed line' not in added_lines
    assert 'context line' not in added_lines


def test_builtin_checkers_use_inherited_helper():
    """
    Test that built-in checkers can use the inherited helper.
    """
    checker = ORMConstraintChecker()

    patch = "+cursor.execute('SELECT * FROM users')"
    added = checker._extract_added_lines(patch)

    assert len(added) == 1
    assert "cursor.execute" in added[0]


def test_orm_checker_detects_cursor():
    """
    Test ORM checker detects cursor usage.
    """
    checker = ORMConstraintChecker()

    patch = """diff --git a/views.py b/views.py
--- a/views.py
+++ b/views.py
@@ -10,3 +10,5 @@
+def bad_view(request):
+    cursor = connection.cursor()
+    cursor.execute("SELECT * FROM users")
"""

    violations = checker.check(patch, {})

    assert len(violations) > 0
    assert any('cursor' in v.lower() for v in violations)


def test_orm_checker_detects_raw():
    """
    Test ORM checker detects .raw() method.
    """
    checker = ORMConstraintChecker()

    patch = """diff --git a/models.py b/models.py
+User.objects.raw('SELECT * FROM users')
"""

    violations = checker.check(patch, {})

    assert len(violations) > 0
    assert any('raw' in v.lower() for v in violations)


def test_orm_checker_clean_code():
    """
    Test ORM checker passes clean ORM code.
    """

    checker = ORMConstraintChecker()

    patch = """diff --git a/models.py b/models.py
+users = User.objects.filter(active=True)
+users = users.select_related('profile')
"""

    violations = checker.check(patch, {})

    assert len(violations) == 0


def test_view_pattern_checker():
    """
    Test view pattern checker detects missing decorators.
    """

    checker = ViewPatternChecker()

    patch = """diff --git a/views.py b/views.py
+def my_view(request):
+    return HttpResponse("Hello")
"""

    violations = checker.check(patch, {})

    assert len(violations) > 0
    assert any('decorator' in v.lower() for v in violations)


def test_naming_convention_checker():
    """
    Test naming convention checker.
    """
    checker = NamingConventionChecker()

    # Bad patch
    bad_patch = """diff --git a/models.py b/models.py
+class MyModel:
+    def addMethod(self):
+        pass
"""

    violations = checker.check(bad_patch, {})
    assert len(violations) > 0

    # Good patch
    good_patch = """diff --git a/models.py b/models.py
+class MyModel:
+    def aDdMeThOd(self):
+        pass
"""

    violations = checker.check(good_patch, {})
    assert len(violations) == 0

def test_naming_convention_checker_private_methods_default():
    """
    Test naming convention checker skips private methods by default.
    """
    checker = NamingConventionChecker()

    # Private method with violations
    patch = """diff --git a/models.py b/models.py
+class MyModel:
+    def _badPrivateMethod(self):
+        pass
"""

    violations = checker.check(patch, {})
    # Should NOT find violations
    assert len(violations) == 0

def test_naming_convention_checker_private_methods_enabled():
    """
    Test naming convention checker for private methods when configured.
    """
    checker = NamingConventionChecker({'check_private_methods': True})

    # Private method with bad naming
    patch = """diff --git a/models.py b/models.py
+class MyModel:
+    def _badPrivateMethod(self):
+        pass
"""

    violations = checker.check(patch, {})
    assert len(violations) > 0
    assert '_badPrivateMethod' in violations[0]


def test_naming_convention_checker_private_methods_good():
    """
    Test private method with good alternating case.
    """
    checker = NamingConventionChecker({'check_private_methods': True})

    # Private method satisfying constraint
    patch = """diff --git a/models.py b/models.py
+class MyModel:
+    def _GoOdPrIvAtE(self):
+        pass
"""

    violations = checker.check(patch, {})
    assert len(violations) == 0


def test_naming_convention_checker_magic_methods_always_skipped():
    """
    Test magic methods are always skipped.
    """
    checker = NamingConventionChecker({'check_private_methods': True})

    patch = """diff --git a/models.py b/models.py
+class MyModel:
+    def __init__(self):
+        pass
+    def __str__(self):
+        pass
"""

    violations = checker.check(patch, {})

    assert len(violations) == 0


def test_constraint_manager_builtin_only():
    """
    Test constraint manager with only built-in checkers.
    """
    config = {
        'builtin': {
            'check_orm_usage': True,
            'check_view_patterns': True,
            'check_naming_convention': False
        },
        'custom': []
    }

    manager = ConstraintManager(config)
    assert len(manager.checkers) == 2
    checker_names = manager.get_checker_names()
    assert 'ORMConstraintChecker' in checker_names
    assert 'ViewPatternChecker' in checker_names
    assert 'NamingConventionChecker' not in checker_names


def test_constraint_manager_all_disabled():
    """
    Test constraint manager with all checkers disabled.
    """
    config = {
        'builtin': {},
        'custom': []
    }

    manager = ConstraintManager(config)

    assert len(manager.checkers) == 0


def test_constraint_manager_check_all():
    """
    Test running all checkers via manager.
    """
    config = {
        'builtin': {
            'check_orm_usage': True,
            'check_view_patterns': False,
            'check_naming_convention': True
        },
        'custom': []
    }

    manager = ConstraintManager(config)

    # Patch with multiple violations
    patch = """diff --git a/code.py b/code.py
+cursor.execute("SELECT * FROM users")
+
+class MyModel:
+    def badNaming(self):
+        pass
"""

    violations = manager.check_all(patch, {})

    assert len(violations) >= 2
    assert any('ORM' in v for v in violations)
    assert any('Naming' in v for v in violations)


def test_constraint_manager_with_builtin_config():
    """
    Test constraint manager passes config to built-in checkers.
    """
    config = {
        'builtin': {
            'check_naming_convention': True
        },
        'builtin_config': {
            'naming_convention': {
                'check_private_methods': True
            }
        },
        'custom': []
    }

    manager = ConstraintManager(config)

    patch = """diff --git a/code.py b/code.py
+class MyModel:
+    def _badPrivate(self):
+        pass
"""

    violations = manager.check_all(patch, {})

    assert len(violations) > 0
    assert '_badPrivate' in violations[0]


def test_custom_checker():
    """
    Test custom user-defined checker functionality.
    """

    # custom checker
    class TestCustomChecker(ConstraintChecker):
        def check(self, patch, context):
            if 'forbidden_word' in patch:
                return ["Custom violation: forbidden word detected"]
            return []

    checker = TestCustomChecker()

    violations = checker.check("some code with forbidden_word", {})
    assert len(violations) == 1
    assert 'forbidden word' in violations[0]

    violations = checker.check("clean code", {})
    assert len(violations) == 0


def test_constraint_manager_empty_patch():
    """
    Test manager handles empty patches.
    """

    config = {
        'builtin': {
            'check_orm_usage': True
        },
        'custom': []
    }

    manager = ConstraintManager(config)
    violations = manager.check_all("", {})

    assert violations == []


def test_constraint_manager_malformed_patch():
    """
    Test manager handles broken patches.
    """
    config = {
        'builtin': {
            'check_orm_usage': True
        },
        'custom': []
    }

    manager = ConstraintManager(config)

    violations = manager.check_all("not a valid patch", {})

    assert isinstance(violations, list)