import ast
from typing import List, Dict, Any
from ..base import ConstraintChecker

class NamingConventionChecker(ConstraintChecker):
    """
    Check alternating case naming convention for class methods.
    """

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.check_private_methods = self.config.get('check_private_methods', False)


    def check(self, patch: str, context: Dict[str, Any] = None ) -> List[str]:
        """
        Check naming convention in patch.
        """

        violations = []
        added_lines = self._extract_added_lines(patch)
        code = "\n".join(added_lines)


        try:
            tree = ast.parse(code)
        except SyntaxError as err:
            return violations

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        method_name = item.name

                        if method_name.startswith('__') and method_name.endswith('__'):
                            continue

                        if method_name.startswith('_') and not self.check_private_methods:
                            continue

                        if not self._is_alternating_case(method_name):
                            violations.append(
                                f"Naming Convention Violation: Method '{method_name}' "
                                f"does not follow alternating case convention (e.g., aDdMeThoD)"
                            )

        return violations

    def _is_alternating_case(self, name: str) -> bool:
        """Check if string uses alternating case."""
        check_name = name.lstrip('_')

        if len(check_name) < 2:
            return True

        for i in range(len(check_name) - 1):
            if check_name[i].isalpha() and check_name[i + 1].isalpha():
                if check_name[i].isupper() == check_name[i + 1].isupper():
                    return False

        return True
