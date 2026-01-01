import subprocess
import shutil
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class RepositoryManager:
    """
    Repository Manager: Handles Git operations for evaluation sessions.

    - Clone repositories at specific commits
    - Apply patches with Git
    - Create checkpoints (Git commits) after each issue
    - Rollback capability for debugging
    - Read file contents from workspace

    Implements the Git snapshot strategy:
    - Clone once per session at base_commit
    - Apply patches incrementally
    - Create Git checkpoint after each issue
    - Support rollback for debugging
    """

    def __init__(self, workspace_base_dir: Path):
        """
        Initialize repository manager.

        Args:
            workspace_base_dir: Base directory for all workspaces
        """
        self.workspace_base_dir = Path(workspace_base_dir)
        self.workspace_base_dir.mkdir(parents=True, exist_ok=True)

        self.checkpoints: List[Dict[str, str]] = []
        self.current_workspace: Optional[Path] = None

    def setup_repository(self, session_id: str, repo_url: str, base_commit: str) -> Path:
        """
        Clone repository at specific commit for a session.

        Args:
            session_id: Unique session identifier
            repo_url: Git repository URL
            base_commit: Git commit hash to checkout

        Returns:
            Path to workspace directory

        Raises:
            RuntimeError: Raise on failure
        """
        workspace_path = self.workspace_base_dir / f"session_{session_id}"

        if workspace_path.exists():
            logger.warning(f"Workspace already exists, cleaning: {workspace_path}")
            shutil.rmtree(workspace_path)

        workspace_path.mkdir(parents=True, exist_ok=True)

        try:
            logger.info(f"Cloning {repo_url} into {workspace_path}")
            subprocess.run(
                ["git", "clone", repo_url, str(workspace_path)],
                check=True,
                capture_output=True,
                text=True
            )

            logger.info(f"Checking out commit {base_commit[:8]}...")
            subprocess.run(
                ["git", "checkout", base_commit],
                cwd=workspace_path,
                check=True,
                capture_output=True,
                text=True
            )

            self._create_checkpoint(
                workspace_path,
                f"Initial state at {base_commit[:8]}"
            )

            self.current_workspace = workspace_path
            logger.info(f"✓ Repository ready at {workspace_path}")

            return workspace_path

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to setup repository: {e.stderr}")

    def apply_patch(self, patch: str, issue_id: str, workspace_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Apply patch to repository and create checkpoint.

        Args:
            patch: patch content
            issue_id: issue identifier
            workspace_path: Path to workspace

        Returns:
            {
                'applied': bool,
                'checkpoint': Optional[str],
                'error': Optional[str]
            }
        """
        if workspace_path is None:
            workspace_path = self.current_workspace

        if workspace_path is None:
            return {
                'applied': False,
                'checkpoint': None,
                'error': 'No workspace initialized'
            }

        patch_file = workspace_path / ".session_bench_patch.tmp"

        try:
            patch_file.write_text(patch)
        except Exception as e:
            return {
                'applied': False,
                'checkpoint': None,
                'error': f'Failed to write patch file: {e}'
            }

        try:
            result = subprocess.run(
                ["git", "apply", "--check", str(patch_file)],
                cwd=workspace_path,
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                logger.error(f"Patch check failed: {result.stderr}")
                patch_file.unlink()
                return {
                    'applied': False,
                    'checkpoint': None,
                    'error': f'Patch validation failed: {result.stderr}'
                }

            subprocess.run(
                ["git", "apply", str(patch_file)],
                cwd=workspace_path,
                check=True,
                capture_output=True,
                text=True
            )

            patch_file.unlink()

            checkpoint_hash = self._create_checkpoint(
                workspace_path,
                f"Applied fix for {issue_id}"
            )

            logger.info(f"Patch applied successfully for {issue_id}")

            return {
                'applied': True,
                'checkpoint': checkpoint_hash,
                'error': None
            }

        except subprocess.CalledProcessError as e:
            if patch_file.exists():
                patch_file.unlink()

            logger.error(f"Failed to apply patch: {e.stderr}")
            return {
                'applied': False,
                'checkpoint': None,
                'error': f'Git apply failed: {e.stderr}'
            }

    def _create_checkpoint(self, workspace_path: Path, message: str) -> str:
        """
        Create Git checkpoint (commit).

        Args:
            workspace_path: path to workspace
            message: commit message

        Returns:
            git commit hash
        """
        try:
            subprocess.run(
                ["git", "add", "-A"],
                cwd=workspace_path,
                check=True,
                capture_output=True
            )

            subprocess.run(
                ["git", "commit", "-m", message, "--allow-empty"],
                cwd=workspace_path,
                check=True,
                capture_output=True
            )

            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=workspace_path,
                check=True,
                capture_output=True,
                text=True
            )

            commit_hash = result.stdout.strip()

            self.checkpoints.append({
                'commit': commit_hash,
                'message': message
            })

            logger.debug(f"Created checkpoint: {commit_hash[:8]} - {message}")

            return commit_hash

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create checkpoint: {e}")
            return ""

    def rollback_to_checkpoint(self, checkpoint_index: int, workspace_path: Optional[Path] = None) -> bool:
        """
        Rollback to a specific checkpoint.

        Args:
            checkpoint_index: index in checkpoints list (0-based)
            workspace_path: path to workspace

        Returns:
            true on success, false otherwise
        """
        if workspace_path is None:
            workspace_path = self.current_workspace

        if workspace_path is None or not self.checkpoints:
            return False

        if checkpoint_index < 0 or checkpoint_index >= len(self.checkpoints):
            logger.error(f"Invalid checkpoint index: {checkpoint_index}")
            return False

        target_commit = self.checkpoints[checkpoint_index]['commit']

        try:
            subprocess.run(
                ["git", "reset", "--hard", target_commit],
                cwd=workspace_path,
                check=True,
                capture_output=True
            )

            logger.info(f"Rolled back to checkpoint {checkpoint_index}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Rollback failed: {e}")
            return False

    def get_file_content(self, filepath: str, workspace_path: Optional[Path] = None) -> Optional[str]:
        """
        Read file content from workspace.

        Args:
            filepath: relative path to file in repository
            workspace_path: path to workspace

        Returns:
            file content as string
        """
        if workspace_path is None:
            workspace_path = self.current_workspace

        if workspace_path is None:
            return None

        full_path = workspace_path / filepath

        try:
            return full_path.read_text()
        except Exception as e:
            logger.error(f"Failed to read {filepath}: {e}")
            return None

    def list_modified_files(self, workspace_path: Optional[Path] = None) -> List[str]:
        """
        Get list of files modified since initial checkout.

        Args:
            workspace_path: path to workspace

        Returns:
            list of modified file paths
        """
        if workspace_path is None:
            workspace_path = self.current_workspace

        if workspace_path is None:
            return []

        try:
            if len(self.checkpoints) < 2:
                return []

            initial_commit = self.checkpoints[0]['commit']

            result = subprocess.run(
                ["git", "diff", "--name-only", initial_commit, "HEAD"],
                cwd=workspace_path,
                check=True,
                capture_output=True,
                text=True
            )

            files = [f.strip() for f in result.stdout.split('\n') if f.strip()]
            return files

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to list modified files: {e}")
            return []

    def get_checkpoint_info(self) -> List[Dict[str, str]]:
        """
        Get information about all checkpoints.

        Returns:
            List of checkpoint info dicts
        """

        return self.checkpoints.copy()

    def cleanup(self, workspace_path: Optional[Path] = None, remove_workspace: bool = True):
        """
        Clean up workspace.

        Args:
            workspace_path: path to workspace
            remove_workspace: delete the workspace directory ?
        """
        if workspace_path is None:
            workspace_path = self.current_workspace

        if workspace_path is None:
            return

        if remove_workspace and workspace_path.exists():
            logger.info(f"Cleaning up workspace: {workspace_path}")
            shutil.rmtree(workspace_path)

        self.current_workspace = None
        self.checkpoints = []