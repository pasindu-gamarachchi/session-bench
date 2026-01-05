import pytest
import json
import csv
from session_bench.storage.writers import ResultsWriter


@pytest.fixture
def temp_results_dir(tmp_path):
    return tmp_path / "results"


@pytest.fixture
def sample_session_results():
    return {
        'session_id': 1,
        'strategy': 'test_strategy',
        'degraded': False,
        'issues_completed': 3,
        'degradation_signal': None,
        'issues': [
            {
                'issue_number': 1,
                'instance_id': 'django-12345',
                'patch': 'diff --git a/file.py\n+new line',
                'test_results': {'all_passed': True},
                'metrics': {'tokens_used': 1000}
            },
            {
                'issue_number': 2,
                'instance_id': 'django-12346',
                'patch': 'diff --git a/file2.py\n+another line',
                'test_results': {'all_passed': True},
                'metrics': {'tokens_used': 1500}
            },
            {
                'issue_number': 3,
                'instance_id': 'django-12347',
                'patch': 'diff --git a/file3.py\n+third line',
                'test_results': {'all_passed': True},
                'metrics': {'tokens_used': 2000}
            }
        ],
        'total_tokens': 4500,
        'total_time': 45.5
    }


def test_results_writer_init(temp_results_dir):
    """
    Test results writer initialization.
    """
    writer = ResultsWriter(temp_results_dir)

    assert writer.results_dir == temp_results_dir
    assert temp_results_dir.exists()


def test_save_session_json(temp_results_dir, sample_session_results):
    """
    Test saving session results as JSON.
    """
    writer = ResultsWriter(temp_results_dir, save_patches=False)

    json_path = writer.save_session_json(sample_session_results, strategy_name="test_strategy")

    assert json_path.exists()
    assert json_path.parent.name == "test_strategy"

    with open(json_path, 'r') as f:
        data = json.load(f)

    assert 'metadata' in data
    assert 'session' in data
    assert data['session']['session_id'] == 1


def test_save_patches(temp_results_dir, sample_session_results):
    """
    Test saving patch files separately.
    """
    writer = ResultsWriter(temp_results_dir, save_patches=True)

    writer.save_session_json(sample_session_results, strategy_name="test_strategy")

    patches_dir = temp_results_dir / "test_strategy" / "patches"

    assert patches_dir.exists()

    patch_files = list(patches_dir.glob("*.patch"))
    assert len(patch_files) == 3


def test_append_to_summary_csv(temp_results_dir, sample_session_results):
    """
    Test appending to summary CSV.
    """
    writer = ResultsWriter(temp_results_dir)

    csv_path = writer.append_to_summary_csv(sample_session_results, strategy_name="test_strategy")
    assert csv_path.exists()
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 1
    assert rows[0]['session_id'] == '1'
    assert rows[0]['strategy'] == 'test_strategy'
    assert rows[0]['issues_completed'] == '3'
    assert rows[0]['degraded'] == 'False'


def test_append_multiple_sessions(temp_results_dir, sample_session_results):
    """
    Test appending multiple sessions to CSV.
    """
    writer = ResultsWriter(temp_results_dir)

    writer.append_to_summary_csv(sample_session_results, "strategy1")

    session2 = sample_session_results.copy()
    session2['session_id'] = 2
    session2['degraded'] = True
    session2['degradation_signal'] = 'test_failure'

    writer.append_to_summary_csv(session2, "strategy2")

    csv_path = temp_results_dir / "summary.csv"
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 2
    assert rows[0]['session_id'] == '1'
    assert rows[1]['session_id'] == '2'
    assert rows[1]['degradation_signal'] == 'test_failure'


def test_load_session_results(temp_results_dir, sample_session_results):
    """
    Test loading session results from JSON.
    """
    writer = ResultsWriter(temp_results_dir)
    writer.save_session_json(sample_session_results, "test_strategy")

    loaded = writer.load_session_results(
        session_id=1,
        strategy_name="test_strategy"
    )

    assert loaded['session_id'] == 1
    assert loaded['total_tokens'] == 4500


def test_load_summary_csv(temp_results_dir, sample_session_results):
    """
    Test loading summary CSV.
    """
    writer = ResultsWriter(temp_results_dir)

    writer.append_to_summary_csv(sample_session_results, "strategy1")

    session2 = sample_session_results.copy()
    session2['session_id'] = 2
    writer.append_to_summary_csv(session2, "strategy2")

    summary = writer.load_summary_csv()

    assert len(summary) == 2
    assert summary[0]['session_id'] == '1'
    assert summary[1]['session_id'] == '2'


def test_get_strategy_summary(temp_results_dir, sample_session_results):
    """
    Test getting strategy summary statistics.
    """
    writer = ResultsWriter(temp_results_dir)

    writer.append_to_summary_csv(sample_session_results, "test_strategy")

    session2 = sample_session_results.copy()
    session2['session_id'] = 2
    session2['degraded'] = True
    session2['issues_completed'] = 2
    writer.append_to_summary_csv(session2, "test_strategy")

    summary = writer.get_strategy_summary("test_strategy")

    assert summary['total_sessions'] == 2
    assert summary['degraded_sessions'] == 1
    assert summary['degradation_rate'] == 0.5
    assert summary['avg_issues_completed'] == 2.5


def test_save_experiment_metadata(temp_results_dir):
    """
    Test saving experiment metadata.
    """
    writer = ResultsWriter(temp_results_dir)

    config = {
        'experiment_name': 'test_experiment',
        'random_seed': 42
    }

    metadata_path = writer.save_experiment_metadata(config, strategy_name="test_strategy")

    assert metadata_path.exists()

    with open(metadata_path, 'r') as f:
        data = json.load(f)

    assert 'config' in data
    assert data['config']['experiment_name'] == 'test_experiment'

