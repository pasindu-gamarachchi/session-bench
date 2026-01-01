import re
from typing import List, Dict, Any
from ..base import ConstraintChecker


class ORMConstraintChecker(ConstraintChecker):
    """
    Check if the generated code uses Django ORM.
    """


    def check(self, patch: str, context: Dict[str, Any]) -> List[str]:
        """
        Check for raw SQL use in patch.
        """

        violations = []

        added_lines = self._extract_added_lines(patch)
        code = '\n'.join(added_lines)

        if re.search(r'cursor\.execute|connection\.cursor', code):
            violations.append(
                "ORM Violation: Raw SQL cursor usage detected "
                "(cursor.execute or connection.cursor)")

        if re.search(r'\.raw\s*\(', code):
            violations.append(
                "ORM Violation: .raw() method detected - use ORM queries instead")

        sql_keywords = r'\b(SELECT|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER)\b'

        if re.search(sql_keywords, code, re.IGNORECASE):
            if re.search(r'["\'].*' + sql_keywords + r'.*["\']', code, re.IGNORECASE):
                violations.append(
                    "ORM Violation: Raw SQL query string detected - use Django ORM")

        return violations
