from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class ConstraintChecker(ABC):
    """
    Abstract class for constraint checkers.
    Users can implement custom checkers by having implementing sub-classes.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}


    @abstractmethod
    def check(self, patch: str, context: Dict[str, Any] = None ) -> List[str]:
        """
        Check patch for constraint violations.

        Args:
            patch: Patch to check
            context: Additional context

        Returns:
            List of violations.
        """
        pass

    def get_constraint_name(self) -> str:
        """ Get constraint name """
        return self.__class__.__name__


    def _extract_added_lines(self, patch: str) -> List[str]:
        """Extract lines that were added from patch."""
        added = []
        for line in patch.split('\n'):
            if line.startswith('+') and not line.startswith('+++'):
                added.append(line[1:])
        return added
