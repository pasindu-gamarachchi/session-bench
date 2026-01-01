import importlib
import logging
from typing import List, Dict, Any, Optional

from .base import ConstraintChecker
from .builtin import ORMConstraintChecker, ViewPatternChecker, NamingConventionChecker

logger = logging.getLogger(__name__)


class ConstraintManager:
    """
    Manager for constraint checker.
    """

    BUILTIN_CHECKERS = {
        'check_orm_usage': ORMConstraintChecker,
        'check_view_patterns': ViewPatternChecker,
        'check_naming_convention': NamingConventionChecker,
    }

    BUILTIN_CONFIG_KEYS = {
        'check_orm_usage': 'orm',
        'check_view_patterns': 'view_patterns',
        'check_naming_convention': 'naming_convention',
    }


    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.checkers: List[ConstraintChecker] = []
        self._load_builtin_checkers()
        self._load_custom_checkers()

        logger.info(f"Loaded {len(self.checkers)} constraint checker(s)")

    def _load_builtin_checkers(self):
        """Load enabled built-in checkers."""
        builtin_config = self.config.get('builtin', {})
        builtin_checker_configs = self.config.get('builtin_config', {})

        for checker_name, checker_class in self.BUILTIN_CHECKERS.items():
            if builtin_config.get(checker_name, False):
                config_key = self.BUILTIN_CONFIG_KEYS.get(checker_name)
                checker_config = builtin_checker_configs.get(config_key, {})

                checker = checker_class(checker_config)
                self.checkers.append(checker)
                logger.debug(f"Loaded built-in checker: {checker.get_constraint_name()}")

    def _load_custom_checkers(self):
        """Load custom user-defined checkers."""
        custom_configs = self.config.get('custom', [])

        for custom_config in custom_configs:
            if not custom_config.get('enabled', True):
                continue

            class_path = custom_config.get('class')
            if not class_path:
                logger.warning("Custom checker missing 'class' field, skipping")
                continue

            try:
                checker_class = self._import_class(class_path)

                checker_config = custom_config.get('config', {})
                checker = checker_class(checker_config)

                self.checkers.append(checker)
                logger.info(f"Loaded custom checker: {checker.get_constraint_name()}")

            except Exception as e:
                logger.error(f"Failed to load custom checker '{class_path}': {e}")

    def _import_class(self, class_path: str):
        """
        Dynamically import a class from a module path. ????

        Args:
            class_path: Full path like 'my_module.MyClass'

        Returns:
            Class object
        """
        module_path, class_name = class_path.rsplit('.', 1)
        module = importlib.import_module(module_path)
        return getattr(module, class_name)


    def check_all(self, patch: str, context: Optional[Dict[str, Any]] = None) -> List[str]:
        """
        Run all enabled checkers on a patch.
        Args:
            patch: Unified diff patch content
            context: Additional context for checkers
        Returns:
            Aggregated list of all violations from all checkers
        """
        if context is None:
            context = {}

        all_violations = []

        for checker in self.checkers:
            try:
                violations = checker.check(patch, context)
                checker_name = checker.get_constraint_name()
                prefixed_violations = [ f"[{checker_name}] {v}" for v in violations]
                all_violations.extend(prefixed_violations)

                if violations:
                    logger.info(f"{checker_name} found {len(violations)} violation(s)")

            except Exception as e:
                logger.error(f"Checker {checker.get_constraint_name()} failed: {e}")

        return all_violations

    def get_checker_names(self) -> List[str]:
        """
        Get names of all loaded checkers.
        """
        return [checker.get_constraint_name() for checker in self.checkers]