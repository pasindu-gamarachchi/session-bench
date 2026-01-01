import ast
from typing import List, Dict, Any

from ..base import ConstraintChecker


class ViewPatternChecker(ConstraintChecker):
    """
    Check that Django views follow expected patterns.
    """

    def check(self, patch: str, context: Dict[str, Any] = None ) -> List[str]:
        violations = []
        added_lines = self._extract_added_lines(patch)
        code = "\n".join(added_lines)


        try:
            tree = ast.parse(code)
        except SyntaxError:
            return violations

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if self._is_view_function(node):
                    if not node.decorator_list:
                        violations.append(
                            f"View Pattern Violation: View function '{node.name}' "
                            f"missing required decorator (e.g., @require_http_methods)" )

        return violations


    def _is_view_function(self, node: ast.FunctionDef) -> bool:
        """Check if function looks like a Django view."""
        if node.args.args:
            first_param = node.args.args[0]
            param_name = first_param.arg if hasattr(first_param, 'arg') else str(first_param)

            return param_name == 'request'
        return False

