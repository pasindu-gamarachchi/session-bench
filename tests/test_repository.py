import pytest
import shutil
from session_bench.repository.manager import RepositoryManager


@pytest.fixture
def temp_workspace(tmp_path):
    """
    Create temporary workspace directory.
    """
    workspace = tmp_path / "workspaces"
    workspace.mkdir()
    yield workspace

    if workspace.exists():
        shutil.rmtree(workspace)


def test_repository_manager_init(temp_workspace):
    """
    Test repository manager initialization.
    """
    manager = RepositoryManager(temp_workspace)

    assert manager.workspace_base_dir == temp_workspace
    assert temp_workspace.exists()
    assert len(manager.checkpoints) == 0


@pytest.mark.slow
def test_setup_repository(temp_workspace):
    """
    Test cloning a real repository.
    """
    manager = RepositoryManager(temp_workspace)

    repo_url = "https://github.com/octocat/Hello-World.git"
    base_commit = "7fd1a60b01f91b314f59955a4e4d4e80d8edf11d"

    workspace = manager.setup_repository(
        session_id="test_1",
        repo_url=repo_url,
        base_commit=base_commit
    )

    assert workspace.exists()
    assert (workspace / ".git").exists()
    assert len(manager.checkpoints) == 1

    manager.cleanup(remove_workspace=True)


def test_apply_patch(temp_workspace):
    """
    Test applying a patch.
    """
    manager = RepositoryManager(temp_workspace)

    repo_url = "https://github.com/octocat/Hello-World.git"
    base_commit = "7fd1a60b01f91b314f59955a4e4d4e80d8edf11d"

    workspace = manager.setup_repository("test_2", repo_url, base_commit)

    # Create a simple patch
    patch = """diff --git a/README b/README
index 980a0d5..4ab0d43 100644
--- a/README
+++ b/README
@@ -1,1 +1,2 @@
 Hello World!
+Added by test
"""

    result = manager.apply_patch(patch, "test-issue-1")

    assert result['applied'] is True
    assert result['checkpoint'] is not None
    assert result['error'] is None
    assert len(manager.checkpoints) == 2

    content = manager.get_file_content("README")
    assert "Added by test" in content

    manager.cleanup(remove_workspace=True)


def test_rollback_to_checkpoint(temp_workspace):
    """
    Test rolling back to a previous checkpoint.
    """
    manager = RepositoryManager(temp_workspace)

    repo_url = "https://github.com/octocat/Hello-World.git"
    base_commit = "7fd1a60b01f91b314f59955a4e4d4e80d8edf11d"

    workspace = manager.setup_repository("test_3", repo_url, base_commit)

    patch1 = """diff --git a/README b/README
index 980a0d5..4ab0d43 100644
--- a/README
+++ b/README
@@ -1,1 +1,2 @@
 Hello World!
+First change
"""
    manager.apply_patch(patch1, "issue-1")

    patch2 = """diff --git a/README b/README
index 4ab0d43..8ab0d43 100644
--- a/README
+++ b/README
@@ -1,2 +1,3 @@
 Hello World!
 First change
+Second change
"""
    manager.apply_patch(patch2, "issue-2")

    assert len(manager.checkpoints) == 3

    success = manager.rollback_to_checkpoint(1)
    assert success is True

    content = manager.get_file_content("README")
    assert "First change" in content
    assert "Second change" not in content

    manager.cleanup(remove_workspace=True)


def test_get_file_content(temp_workspace):
    """
    Test reading file content.
    """
    manager = RepositoryManager(temp_workspace)

    repo_url = "https://github.com/octocat/Hello-World.git"
    base_commit = "7fd1a60b01f91b314f59955a4e4d4e80d8edf11d"

    workspace = manager.setup_repository("test_4", repo_url, base_commit)

    content = manager.get_file_content("README")

    assert content is not None
    assert "Hello World" in content

    content = manager.get_file_content("nonexistent.txt")
    assert content is None

    manager.cleanup(remove_workspace=True)


def test_list_modified_files(temp_workspace):
    """
    Test listing modified files.
    """
    manager = RepositoryManager(temp_workspace)

    repo_url = "https://github.com/octocat/Hello-World.git"
    base_commit = "7fd1a60b01f91b314f59955a4e4d4e80d8edf11d"

    workspace = manager.setup_repository("test_5", repo_url, base_commit)

    modified = manager.list_modified_files()
    assert len(modified) == 0

    # Apply patch
    patch = """diff --git a/README b/README
index 980a0d5..4ab0d43 100644
--- a/README
+++ b/README
@@ -1,1 +1,2 @@
 Hello World!
+Modified
"""
    manager.apply_patch(patch, "test-issue")

    modified = manager.list_modified_files()
    assert "README" in modified

    manager.cleanup(remove_workspace=True)