import json
import csv
from pathlib import Path
from typing import Dict, Any, List
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ResultsWriter:
    """
    Writes evaluation results.
    """

    def __init__(self, results_dir: Path, save_patches: bool = True, save_logs: bool = True):
        """
        Args:
            results_dir: Base directory for results
            save_patches: Whether to save patch files separately
            save_logs: Whether to save detailed logs
        """
        self.results_dir = Path(results_dir)
        self.save_patches = save_patches
        self.save_logs = save_logs

        self.results_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"ResultsWriter initialized: {self.results_dir}")

    def save_session_json(self, session_results: Dict[str, Any], strategy_name: str) -> Path:
        """
        Save session results as JSON.

        Args:
            session_results: Session results dictionary
            strategy_name: Name of strategy (for directory organization)
        Returns:
            Path to saved JSON file
        """

        strategy_dir = self.results_dir / strategy_name
        strategy_dir.mkdir(parents=True, exist_ok=True)

        session_id = session_results['session_id']
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        json_filename = f"session_{session_id}_{timestamp}.json"
        json_path = strategy_dir / json_filename

        output_data = {
            'metadata': {
                'saved_at': datetime.now().isoformat(),
                'framework_version': '0.1.0',
                'strategy': strategy_name
            },
            'session': session_results
        }

        with open(json_path, 'w') as f:
            json.dump(output_data, f, indent=2)

        logger.info(f"Saved session results: {json_path}")

        if self.save_patches:
            self._save_patches(session_results, strategy_dir)

        return json_path

    def _save_patches(self, session_results: Dict[str, Any], strategy_dir: Path):
        """
        Save patch files.
        Args:
            session_results: Session results
            strategy_dir: Strategy directory
        """

        patches_dir = strategy_dir / "patches"
        patches_dir.mkdir(exist_ok=True)

        session_id = session_results['session_id']

        for issue_result in session_results['issues']:
            issue_number = issue_result['issue_number']
            instance_id = issue_result['instance_id']
            patch = issue_result['patch']

            patch_filename = f"session_{session_id}_issue_{issue_number}_{instance_id}.patch"
            patch_path = patches_dir / patch_filename

            patch_path.write_text(patch)

        logger.debug(f"Saved {len(session_results['issues'])} patch files")

    def append_to_summary_csv(self, session_results: Dict[str, Any], strategy_name: str ) -> Path:
        """
        Append session summary to CSV file.
        Args:
            session_results: Session results
            strategy_name: Strategy name
        Returns:
            Path to CSV file
        """

        csv_path = self.results_dir / "summary.csv"

        file_exists = csv_path.exists()

        fieldnames = [
            'session_id',
            'strategy',
            'issues_completed',
            'total_issues',
            'degraded',
            'degradation_signal',
            'total_tokens',
            'total_time',
            'avg_tokens_per_issue',
            'avg_time_per_issue',
            'timestamp'
        ]

        total_issues = len(session_results['issues'])
        issues_completed = session_results['issues_completed']

        summary_row = {
            'session_id': session_results['session_id'],
            'strategy': strategy_name,
            'issues_completed': issues_completed,
            'total_issues': total_issues,
            'degraded': session_results['degraded'],
            'degradation_signal': session_results.get('degradation_signal', ''),
            'total_tokens': session_results['total_tokens'],
            'total_time': round(session_results['total_time'], 2),
            'avg_tokens_per_issue': (
                round(session_results['total_tokens'] / issues_completed, 2)
                if issues_completed > 0 else 0
            ),
            'avg_time_per_issue': (
                round(session_results['total_time'] / issues_completed, 2)
                if issues_completed > 0 else 0
            ),
            'timestamp': datetime.now().isoformat()
        }

        with open(csv_path, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)

            if not file_exists:
                writer.writeheader()

            writer.writerow(summary_row)

        logger.info(f"Appended to summary CSV: {csv_path}")

        return csv_path

    def save_experiment_metadata(self, config: Dict[str, Any], strategy_name: str) -> Path:
        """
        Save experiment configuration metadata.
        Args:
            config: Experiment configuration
            strategy_name: Strategy name
        Returns:
            Path to saved metadata file
        """

        strategy_dir = self.results_dir / strategy_name
        strategy_dir.mkdir(parents=True, exist_ok=True)

        metadata_path = strategy_dir / "experiment_metadata.json"

        metadata = {
            'saved_at': datetime.now().isoformat(),
            'strategy': strategy_name,
            'config': config
        }

        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"Saved experiment metadata: {metadata_path}")

        return metadata_path

    def load_session_results(self, session_id: int, strategy_name: str) -> Dict[str, Any]:
        """
        Load session results from JSON.
        Args:
            session_id: Session ID
            strategy_name: Strategy name
        Returns:
            Session results dictionary
        """
        strategy_dir = self.results_dir / strategy_name

        matching_files = list(strategy_dir.glob(f"session_{session_id}_*.json"))

        if not matching_files:
            raise FileNotFoundError(
                f"No results found for session {session_id} with strategy {strategy_name}"
            )

        json_path = sorted(matching_files)[-1]

        with open(json_path, 'r') as f:
            data = json.load(f)

        return data['session']

    def load_summary_csv(self) -> List[Dict[str, Any]]:
        """
        Load summary CSV.
        Returns:
            List of session summaries

        """
        csv_path = self.results_dir / "summary.csv"

        if not csv_path.exists():
            raise FileNotFoundError(f"Summary CSV not found: {csv_path}")

        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            return list(reader)

    def get_strategy_summary(self, strategy_name: str) -> Dict[str, Any]:
        """
        Get summary statistics for a strategy.
        Args:
            strategy_name: Strategy name
        Returns:
            Summary statistics
        """
        try:
            all_results = self.load_summary_csv()
        except FileNotFoundError:
            return {}

        strategy_results = [
            r for r in all_results
            if r['strategy'] == strategy_name
        ]

        if not strategy_results:
            return {}

        total_sessions = len(strategy_results)
        degraded_sessions = sum(1 for r in strategy_results if r['degraded'].lower() == 'true')

        avg_issues_completed = sum(int(r['issues_completed']) for r in strategy_results) / total_sessions

        avg_tokens = sum(float(r['total_tokens']) for r in strategy_results) / total_sessions

        return {
            'strategy': strategy_name,
            'total_sessions': total_sessions,
            'degraded_sessions': degraded_sessions,
            'degradation_rate': degraded_sessions / total_sessions,
            'avg_issues_completed': round(avg_issues_completed, 2),
            'avg_tokens': round(avg_tokens, 2)
        }