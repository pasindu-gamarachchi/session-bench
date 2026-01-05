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

        self._clone_repository(repo_url, workspace_path)
        self._checkout_commit(workspace_path, base_commit)

        installation_success = self._install_dependencies(workspace_path)
        if not installation_success:
            logger.warning("Dependency installation failed - tests may not run correctly")

        self._create_checkpoint(workspace_path=workspace_path, checkpoint_name="initial",
                                message="Initial repository state")

        logger.info(f"Repository ready at {workspace_path}")
        return workspace_path

    def _clone_repository(self, repo_url: str, workspace_path: Path):
        """
        Clone a git repository.
        Args:
            repo_url: Git repository URL
            workspace_path: Destination path
        Raises:
            RuntimeError: If cloning fails
        """
        logger.info(f"Cloning {repo_url} into {workspace_path}")

        try:
            subprocess.run(["git", "clone", repo_url, str(workspace_path)], check=True, capture_output=True, text=True,
                           timeout=600)
        except subprocess.CalledProcessError as err:
            raise RuntimeError(f"Failed to clone repository: {err.stderr}")
        except subprocess.TimeoutExpired:
            raise RuntimeError("Repository clone timed out after 10 minutes")

    def _checkout_commit(self, workspace_path: Path, commit: str):
        """
        Checkout a specific commit.
        Args:
            workspace_path: Repository path
            commit: Commit to checkout
        Raises:
            RuntimeError: If checkout fails
        """
        logger.info(f"Checking out commit {commit[:8]}...")

        try:
            subprocess.run(["git", "checkout", commit], cwd=workspace_path, check=True, capture_output=True, text=True)
            logger.info(f"Repository ready at {workspace_path}")
        except subprocess.CalledProcessError as err:
            raise RuntimeError(f"Failed to checkout commit {commit}: {err.stderr}")

    def _create_checkpoint(self, workspace_path: Path, checkpoint_name: str, message: str):
        """
        Create a git commit checkpoint.
        Args:
            workspace_path: Repository path
            checkpoint_name: Name for the checkpoint
            message: Commit message
        """
        try:
            subprocess.run(["git", "add", "-A"], cwd=workspace_path, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", message, "--allow-empty"], cwd=workspace_path, check=True,
                           capture_output=True)

            logger.debug(f"Created checkpoint: {checkpoint_name}")
        except subprocess.CalledProcessError as err:
            logger.warning(f"Failed to create checkpoint: {err}")

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
        except Exception as err:
            return {
                'applied': False,
                'checkpoint': None,
                'error': f'Failed to write patch file: {err}'
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

    # def _create_checkpoint(self, workspace_path: Path, message: str) -> str:
    #    """
    #    Create Git checkpoint (commit).

    #    Args:
    #        workspace_path: path to workspace
    #        message: commit message

    #    Returns:
    #        git commit hash
    #    """
    #    try:
    #        subprocess.run(
    #            ["git", "add", "-A"],
    #            cwd=workspace_path,
    #            check=True,
    #            capture_output=True
    #        )

    #        subprocess.run(
    #            ["git", "commit", "-m", message, "--allow-empty"],
    #            cwd=workspace_path,
    #            check=True,
    #            capture_output=True
    #        )

    #        result = subprocess.run(
    #            ["git", "rev-parse", "HEAD"],
    #            cwd=workspace_path,
    #            check=True,
    #            capture_output=True,
    #            text=True
    #        )

    #        commit_hash = result.stdout.strip()

    #        self.checkpoints.append({
    #            'commit': commit_hash,
    #            'message': message
    #        })

    #        logger.debug(f"Created checkpoint: {commit_hash[:8]} - {message}")

    #        return commit_hash

    # except subprocess.CalledProcessError as e:
    #     logger.error(f"Failed to create checkpoint: {e}")
    #     return ""

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

        except subprocess.CalledProcessError as err:
            logger.error(f"Rollback failed: {err}")
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
        except Exception as err:
            logger.error(f"Failed to read {filepath}: {err}")
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

        except subprocess.CalledProcessError as err:
            logger.error(f"Failed to list modified files: {err}")
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

    def _install_dependencies(self, workspace_path: Path) -> bool:
        """
        Install project dependencies.
        Tries multiple installation methods:
        1. pip install -e .
        2. pip install -r requirements.txt
        3. pip install -r tests/requirements.txt
        Args:
            workspace_path: Path to repository workspace
        Returns:
            True if installation succeeded, False otherwise
        """
        logger.info("Installing project dependencies...")
        timeout = 3000
        try:
            logger.info("Trying: pip install -e .")
            result = subprocess.run(["pip", "install", "-e", ".", "--quiet"], cwd=workspace_path, capture_output=True,
                                    text=True, timeout=timeout)

            if result.returncode == 0:
                logger.info("Dependencies installed via 'pip install -e .'")
                return True
            else:
                logger.warning(f"pip install -e . failed: {result.stderr[:200]}")

        except subprocess.TimeoutExpired:
            logger.error(f"pip install -e . timed out after {timeout / 60} minutes")
        except Exception as err:
            logger.warning(f"pip install -e . error: {err}")

        requirements_txt = workspace_path / "requirements.txt"
        if requirements_txt.exists():
            try:
                logger.info("Trying: pip install -r requirements.txt")
                result = subprocess.run(["pip", "install", "-r", "requirements.txt", "--quiet"], cwd=workspace_path,
                                        capture_output=True, text=True, timeout=timeout)

                if result.returncode == 0:
                    logger.info("Dependencies installed via requirements.txt")
                    return True
                else:
                    logger.warning(f"requirements.txt install failed: {result.stderr[:200]}")

            except Exception as err:
                logger.warning(f"requirements.txt install error: {err}")

        tests_requirements = workspace_path / "tests" / "requirements.txt"
        if tests_requirements.exists():
            try:
                logger.info("Trying: pip install -r tests/requirements.txt")
                result = subprocess.run(["pip", "install", "-r", "tests/requirements.txt", "--quiet"],
                                        cwd=workspace_path, capture_output=True, text=True,
                                        timeout=timeout)

                if result.returncode == 0:
                    logger.info("Dependencies installed via tests/requirements.txt")
                    return True
                else:
                    logger.warning(f"tests/requirements.txt install failed: {result.stderr[:200]}")

            except Exception as e:
                logger.warning(f"tests/requirements.txt install error: {e}")

        setup_py = workspace_path / "setup.py"
        if setup_py.exists():
            try:
                logger.info("Trying: python setup.py develop")
                result = subprocess.run(["python", "setup.py", "develop"], cwd=workspace_path, capture_output=True,
                                        text=True, timeout=timeout)
                if result.returncode == 0:
                    logger.info("Dependencies installed via setup.py develop")
                    return True

            except Exception as err:
                logger.warning(f"setup.py develop error: {err}")

        logger.error("Failed to install dependencies via any method")
        return False

    def setup_repository_from_cache(self, session_id: str, cache_path: Path, base_commit: Optional[str] = None) -> Path:
        """Setup repository by copying from cache instead of cloning."""
        if not cache_path.exists():
            raise FileNotFoundError(f"Cache path does not exist: {cache_path}")

        if not (cache_path / ".git").exists():
            raise ValueError(f"Cache path is not a git repository: {cache_path}")

        workspace_path = self.workspace_base_dir / f"session_{session_id}"

        if workspace_path.exists():
            logger.warning(f"Workspace {workspace_path} already exists, removing...")
            shutil.rmtree(workspace_path)

        logger.info(f"Copying repository from cache: {cache_path}")
        shutil.copytree(cache_path, workspace_path)
        logger.info(f"Repository copied to: {workspace_path}")

        if base_commit:
            current_commit = self._get_current_commit(workspace_path)
            if current_commit != base_commit:
                logger.info(f"Checking out commit: {base_commit}")
                self._checkout_commit(workspace_path, base_commit)

        installation_success = self._install_dependencies(workspace_path)
        if not installation_success:
            logger.warning("Dependency installation failed - tests may not run correctly")

        self._create_checkpoint(workspace_path=workspace_path, checkpoint_name="initial",
                                message="Initial repository state from cache")

        logger.info(f"Repository setup complete: {workspace_path}")
        return workspace_path
