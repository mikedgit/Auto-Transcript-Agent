"""Tests for the folder monitoring system."""

import time
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from src.monitor import FolderMonitor, ProcessedFile
from src.transcriber import AudioTranscriber


class TestProcessedFile:
    """Test the ProcessedFile dataclass."""

    def test_processed_file_creation(self):
        """Test creating a ProcessedFile instance."""
        file_path = Path("/test/file.mp3")
        processed_at = time.time()

        processed_file = ProcessedFile(
            path=file_path, processed_at=processed_at, status="success"
        )

        assert processed_file.path == file_path
        assert processed_file.processed_at == processed_at
        assert processed_file.status == "success"
        assert processed_file.error_message is None


class TestFolderMonitor:
    """Test the FolderMonitor class."""

    @pytest.fixture
    def mock_transcriber(self):
        """Create a mock transcriber for testing."""
        mock = Mock(spec=AudioTranscriber)
        mock.is_supported_file.return_value = True
        mock.transcribe_and_save.return_value = {
            "status": "success",
            "input_file": "test.mp3",
            "output_file": "test.txt",
            "transcript_length": 100,
            "duration_seconds": 5.0,
            "error": None,
        }
        return mock

    def test_init(self, tmp_path, mock_transcriber):
        """Test FolderMonitor initialization."""
        input_dir = tmp_path / "input"
        output_dir = tmp_path / "output"
        done_dir = tmp_path / "done"

        monitor = FolderMonitor(
            input_dir=input_dir,
            output_dir=output_dir,
            done_dir=done_dir,
            transcriber=mock_transcriber,
            poll_interval=10,
        )

        assert monitor.input_dir == input_dir
        assert monitor.output_dir == output_dir
        assert monitor.done_dir == done_dir
        assert monitor.transcriber == mock_transcriber
        assert monitor.poll_interval == 10

        # Directories should be created
        assert input_dir.exists()
        assert output_dir.exists()
        assert done_dir.exists()

    def test_process_existing_files(self, tmp_path, mock_transcriber):
        """Test processing files that already exist in input directory."""
        input_dir = tmp_path / "input"
        output_dir = tmp_path / "output"
        done_dir = tmp_path / "done"

        # Create some test files
        test_file1 = input_dir / "test1.mp3"
        test_file2 = input_dir / "test2.wav"
        test_file3 = input_dir / "test.txt"  # Not an audio file

        input_dir.mkdir()
        test_file1.write_text("fake audio 1")
        test_file2.write_text("fake audio 2")
        test_file3.write_text("not audio")

        # Mock transcriber to only support audio files
        def mock_is_supported(path):
            return path.suffix.lower() in [".mp3", ".wav"]

        mock_transcriber.is_supported_file.side_effect = mock_is_supported

        monitor = FolderMonitor(
            input_dir=input_dir,
            output_dir=output_dir,
            done_dir=done_dir,
            transcriber=mock_transcriber,
        )

        # Process existing files
        monitor._process_existing_files()

        # Should have processed 2 audio files
        assert len(monitor.processed_files) == 2
        assert mock_transcriber.transcribe_and_save.call_count == 2

    def test_move_to_done(self, tmp_path, mock_transcriber):
        """Test moving processed files to done directory."""
        input_dir = tmp_path / "input"
        output_dir = tmp_path / "output"
        done_dir = tmp_path / "done"

        test_file = input_dir / "test.mp3"
        input_dir.mkdir()
        test_file.write_text("fake audio")

        monitor = FolderMonitor(
            input_dir=input_dir,
            output_dir=output_dir,
            done_dir=done_dir,
            transcriber=mock_transcriber,
        )

        # Move file to done directory
        monitor._move_to_done(test_file)

        # Original file should be moved
        assert not test_file.exists()
        assert (done_dir / "test.mp3").exists()

    def test_move_to_done_conflict(self, tmp_path, mock_transcriber):
        """Test moving files when filename conflicts exist."""
        input_dir = tmp_path / "input"
        output_dir = tmp_path / "output"
        done_dir = tmp_path / "done"

        # Create conflicting file in done directory
        done_dir.mkdir(parents=True)
        (done_dir / "test.mp3").write_text("existing file")

        test_file = input_dir / "test.mp3"
        input_dir.mkdir()
        test_file.write_text("fake audio")

        monitor = FolderMonitor(
            input_dir=input_dir,
            output_dir=output_dir,
            done_dir=done_dir,
            transcriber=mock_transcriber,
        )

        # Move file to done directory
        monitor._move_to_done(test_file)

        # Should create a new filename to avoid conflict
        assert not test_file.exists()
        assert (done_dir / "test_1.mp3").exists()
        assert (done_dir / "test.mp3").exists()  # Original conflict file still there

    def test_is_recently_processed(self, tmp_path, mock_transcriber):
        """Test checking if a file was recently processed."""
        monitor = FolderMonitor(
            input_dir=tmp_path / "input",
            output_dir=tmp_path / "output",
            done_dir=tmp_path / "done",
            transcriber=mock_transcriber,
        )

        test_file = Path("/test/file.mp3")

        # File not processed yet
        assert not monitor._is_recently_processed(test_file)

        # Add to processed files
        monitor.processed_files.append(
            ProcessedFile(path=test_file, processed_at=time.time(), status="success")
        )

        # Should now be considered recently processed
        assert monitor._is_recently_processed(test_file)

        # Add old processed file (more than 1 hour ago)
        old_file = Path("/test/old_file.mp3")
        monitor.processed_files.append(
            ProcessedFile(
                path=old_file,
                processed_at=time.time() - 7200,  # 2 hours ago
                status="success",
            )
        )

        # Old file should not be considered recently processed
        assert not monitor._is_recently_processed(old_file)

    def test_get_statistics(self, tmp_path, mock_transcriber):
        """Test getting processing statistics."""
        monitor = FolderMonitor(
            input_dir=tmp_path / "input",
            output_dir=tmp_path / "output",
            done_dir=tmp_path / "done",
            transcriber=mock_transcriber,
        )

        # Add some processed files
        test_files = [
            ProcessedFile(Path("/test1.mp3"), time.time(), "success"),
            ProcessedFile(Path("/test2.mp3"), time.time(), "success"),
            ProcessedFile(Path("/test3.mp3"), time.time(), "error", "API error"),
            ProcessedFile(Path("/test4.mp3"), time.time(), "skipped", "Already exists"),
        ]
        monitor.processed_files.extend(test_files)

        stats = monitor.get_statistics()

        assert stats["total_processed"] == 4
        assert stats["successful"] == 2
        assert stats["errors"] == 1
        assert stats["skipped"] == 1
        assert stats["success_rate"] == 0.5
        assert "is_monitoring" in stats

    def test_get_recent_files(self, tmp_path, mock_transcriber):
        """Test getting recently processed files."""
        monitor = FolderMonitor(
            input_dir=tmp_path / "input",
            output_dir=tmp_path / "output",
            done_dir=tmp_path / "done",
            transcriber=mock_transcriber,
        )

        now = time.time()

        # Add files with different processing times
        test_files = [
            ProcessedFile(Path("/recent1.mp3"), now - 1800, "success"),  # 30 min ago
            ProcessedFile(Path("/recent2.mp3"), now - 3600, "success"),  # 1 hour ago
            ProcessedFile(Path("/old.mp3"), now - 25 * 3600, "success"),  # 25 hours ago
        ]
        monitor.processed_files.extend(test_files)

        # Get files from last 24 hours
        recent_files = monitor.get_recent_files(hours=24)

        assert len(recent_files) == 2
        assert all(f.path.name.startswith("recent") for f in recent_files)

    @patch("src.monitor.time.sleep")
    @patch("pathlib.Path.stat")
    def test_wait_for_file_stability(
        self, mock_stat, mock_sleep, tmp_path, mock_transcriber
    ):
        """Test waiting for file to become stable."""
        monitor = FolderMonitor(
            input_dir=tmp_path / "input",
            output_dir=tmp_path / "output",
            done_dir=tmp_path / "done",
            transcriber=mock_transcriber,
        )

        test_file = tmp_path / "test.mp3"
        test_file.write_text("initial content")

        # Mock stat to return same size multiple times (stable file)
        mock_stat_result = Mock()
        mock_stat_result.st_size = 100
        mock_stat.return_value = mock_stat_result

        monitor._wait_for_file_stability(test_file)

        # Should have called sleep at least a few times
        assert mock_sleep.call_count >= 3

    def test_record_processed_file(self, tmp_path, mock_transcriber):
        """Test recording processed file information."""
        monitor = FolderMonitor(
            input_dir=tmp_path / "input",
            output_dir=tmp_path / "output",
            done_dir=tmp_path / "done",
            transcriber=mock_transcriber,
        )

        test_file = Path("/test/file.mp3")

        # Record a successful processing
        monitor._record_processed_file(test_file, "success")

        assert len(monitor.processed_files) == 1
        processed = monitor.processed_files[0]
        assert processed.path == test_file
        assert processed.status == "success"
        assert processed.error_message is None

        # Record an error
        monitor._record_processed_file(test_file, "error", "Test error")

        assert len(monitor.processed_files) == 2
        error_processed = monitor.processed_files[1]
        assert error_processed.status == "error"
        assert error_processed.error_message == "Test error"

    def test_processed_files_limit(self, tmp_path, mock_transcriber):
        """Test that processed files list is limited to prevent memory issues."""
        monitor = FolderMonitor(
            input_dir=tmp_path / "input",
            output_dir=tmp_path / "output",
            done_dir=tmp_path / "done",
            transcriber=mock_transcriber,
        )

        # Add more than 1000 processed files
        for i in range(1100):
            monitor._record_processed_file(Path(f"/test/file_{i}.mp3"), "success")

        # Should be limited to 1000 files
        assert len(monitor.processed_files) == 1000

        # Should keep the most recent files
        assert monitor.processed_files[0].path.name == "file_100.mp3"
        assert monitor.processed_files[-1].path.name == "file_1099.mp3"
