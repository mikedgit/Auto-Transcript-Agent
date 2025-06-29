"""Extended tests for monitor functionality to improve coverage."""

import pytest
from unittest.mock import Mock, patch
from threading import Event

from src.monitor import FolderMonitor, AudioFileHandler
from src.transcriber import AudioTranscriber, TranscriberError


class TestAudioFileHandler:
    """Test the AudioFileHandler class."""

    @pytest.fixture
    def mock_transcriber(self):
        """Create a mock transcriber."""
        mock = Mock(spec=AudioTranscriber)
        mock.is_supported_file.return_value = True
        return mock

    @pytest.fixture
    def callback_mock(self):
        """Create a mock callback function."""
        return Mock()

    def test_audio_file_handler_init(self, mock_transcriber, callback_mock):
        """Test AudioFileHandler initialization."""
        handler = AudioFileHandler(mock_transcriber, callback_mock)

        assert handler.transcriber == mock_transcriber
        assert handler.callback == callback_mock
        assert handler.processing_files == set()

    def test_on_created_directory_ignored(self, mock_transcriber, callback_mock):
        """Test that directory creation events are ignored."""
        handler = AudioFileHandler(mock_transcriber, callback_mock)

        # Mock directory event
        event = Mock()
        event.is_directory = True
        event.src_path = "/test/dir"

        handler.on_created(event)

        # Callback should not be called for directories
        callback_mock.assert_not_called()

    def test_on_created_unsupported_file(self, mock_transcriber, callback_mock):
        """Test that unsupported files are ignored."""
        handler = AudioFileHandler(mock_transcriber, callback_mock)
        mock_transcriber.is_supported_file.return_value = False

        event = Mock()
        event.is_directory = False
        event.src_path = "/test/file.txt"

        handler.on_created(event)

        # Callback should not be called for unsupported files
        callback_mock.assert_not_called()

    def test_on_created_temporary_file(self, mock_transcriber, callback_mock):
        """Test that temporary files are ignored."""
        handler = AudioFileHandler(mock_transcriber, callback_mock)

        event = Mock()
        event.is_directory = False
        event.src_path = "/test/.temp_file.mp3"

        handler.on_created(event)

        # Callback should not be called for temp files
        callback_mock.assert_not_called()

        # Test tilde prefix too
        event.src_path = "/test/~temp_file.mp3"
        handler.on_created(event)
        callback_mock.assert_not_called()

    def test_on_created_already_processing(self, mock_transcriber, callback_mock):
        """Test that files already being processed are ignored."""
        handler = AudioFileHandler(mock_transcriber, callback_mock)

        # Add file to processing set
        file_path = "/test/file.mp3"
        handler.processing_files.add(file_path)

        event = Mock()
        event.is_directory = False
        event.src_path = file_path

        handler.on_created(event)

        # Callback should not be called for files already processing
        callback_mock.assert_not_called()

    def test_on_created_success(self, mock_transcriber, callback_mock):
        """Test successful file creation handling."""
        handler = AudioFileHandler(mock_transcriber, callback_mock)

        event = Mock()
        event.is_directory = False
        event.src_path = "/test/file.mp3"

        handler.on_created(event)

        # Callback should be called
        callback_mock.assert_called_once()
        called_path = callback_mock.call_args[0][0]
        assert str(called_path) == "/test/file.mp3"

    def test_on_modified(self, mock_transcriber, callback_mock):
        """Test file modification handling."""
        handler = AudioFileHandler(mock_transcriber, callback_mock)

        event = Mock()
        event.is_directory = False
        event.src_path = "/test/file.mp3"

        handler.on_modified(event)

        # Callback should be called for modifications too
        callback_mock.assert_called_once()


class TestFolderMonitorExtended:
    """Extended tests for FolderMonitor class."""

    @pytest.fixture
    def mock_transcriber(self):
        """Create a mock transcriber."""
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

    def test_start_and_stop(self, tmp_path, mock_transcriber):
        """Test starting and stopping the monitor."""
        monitor = FolderMonitor(
            input_dir=tmp_path / "input",
            output_dir=tmp_path / "output",
            done_dir=tmp_path / "done",
            transcriber=mock_transcriber,
        )

        # Mock observer to avoid actual file watching
        with patch.object(monitor, "observer") as mock_observer:
            monitor.start()

            mock_observer.schedule.assert_called_once()
            mock_observer.start.assert_called_once()

            # Stop should stop observer
            monitor.stop()
            mock_observer.stop.assert_called_once()
            mock_observer.join.assert_called_once()

    def test_process_file_nonexistent(self, tmp_path, mock_transcriber):
        """Test processing a file that doesn't exist."""
        monitor = FolderMonitor(
            input_dir=tmp_path / "input",
            output_dir=tmp_path / "output",
            done_dir=tmp_path / "done",
            transcriber=mock_transcriber,
        )

        nonexistent_file = tmp_path / "input" / "nonexistent.mp3"

        # Should handle gracefully
        monitor._process_file(nonexistent_file)

        # No processing should have occurred
        assert len(monitor.processed_files) == 0

    def test_process_file_transcript_exists(self, tmp_path, mock_transcriber):
        """Test processing when transcript already exists."""
        monitor = FolderMonitor(
            input_dir=tmp_path / "input",
            output_dir=tmp_path / "output",
            done_dir=tmp_path / "done",
            transcriber=mock_transcriber,
        )

        # Create input file and existing transcript
        input_file = tmp_path / "input" / "test.mp3"
        input_file.write_text("fake audio")

        output_file = tmp_path / "output" / "test.txt"
        output_file.parent.mkdir(parents=True)
        output_file.write_text("existing transcript")

        with (
            patch.object(monitor, "_wait_for_file_stability"),
            patch.object(monitor, "_move_to_done") as mock_move,
        ):

            monitor._process_file(input_file)

            # Should skip transcription and move to done
            mock_transcriber.transcribe_and_save.assert_not_called()
            mock_move.assert_called_once_with(input_file)

    def test_process_file_transcription_error(self, tmp_path, mock_transcriber):
        """Test processing with transcription error."""
        monitor = FolderMonitor(
            input_dir=tmp_path / "input",
            output_dir=tmp_path / "output",
            done_dir=tmp_path / "done",
            transcriber=mock_transcriber,
        )

        # Make transcriber raise error
        mock_transcriber.transcribe_and_save.side_effect = TranscriberError("API error")

        input_file = tmp_path / "input" / "test.mp3"
        input_file.write_text("fake audio")

        with patch.object(monitor, "_wait_for_file_stability"):
            monitor._process_file(input_file)

        # Should record error
        assert len(monitor.processed_files) == 1
        assert monitor.processed_files[0].status == "error"
        assert "API error" in monitor.processed_files[0].error_message

    def test_wait_for_file_stability_missing_file(self, tmp_path, mock_transcriber):
        """Test file stability check when file disappears."""
        monitor = FolderMonitor(
            input_dir=tmp_path / "input",
            output_dir=tmp_path / "output",
            done_dir=tmp_path / "done",
            transcriber=mock_transcriber,
        )

        nonexistent_file = tmp_path / "nonexistent.mp3"

        # Should handle missing file gracefully
        monitor._wait_for_file_stability(nonexistent_file)

    @patch("src.monitor.time.sleep")
    def test_wait_for_file_stability_changing_size(
        self, mock_sleep, tmp_path, mock_transcriber
    ):
        """Test file stability with changing file size."""
        monitor = FolderMonitor(
            input_dir=tmp_path / "input",
            output_dir=tmp_path / "output",
            done_dir=tmp_path / "done",
            transcriber=mock_transcriber,
        )

        test_file = tmp_path / "test.mp3"
        test_file.write_text("initial")

        # Mock file stat to simulate changing then stable size
        call_count = 0

        def mock_stat():
            nonlocal call_count
            call_count += 1
            mock_result = Mock()
            if call_count <= 2:
                mock_result.st_size = call_count * 100  # Changing size
            else:
                mock_result.st_size = 200  # Stable size
            return mock_result

        with patch.object(test_file, "stat", side_effect=mock_stat):
            monitor._wait_for_file_stability(test_file, max_wait=5)

        # Should have called sleep while waiting for stability
        assert mock_sleep.call_count >= 3

    def test_move_to_done_error(self, tmp_path, mock_transcriber):
        """Test move to done with file system error."""
        monitor = FolderMonitor(
            input_dir=tmp_path / "input",
            output_dir=tmp_path / "output",
            done_dir=tmp_path / "done",
            transcriber=mock_transcriber,
        )

        test_file = tmp_path / "input" / "test.mp3"
        test_file.write_text("fake audio")

        # Mock rename to raise exception
        with patch.object(
            test_file, "rename", side_effect=OSError("Permission denied")
        ):
            # Should handle error gracefully
            monitor._move_to_done(test_file)

    @patch("src.monitor.time.sleep")
    def test_poll_directory_error_handling(
        self, mock_sleep, tmp_path, mock_transcriber
    ):
        """Test polling directory with error handling."""
        monitor = FolderMonitor(
            input_dir=tmp_path / "input",
            output_dir=tmp_path / "output",
            done_dir=tmp_path / "done",
            transcriber=mock_transcriber,
            poll_interval=0.1,
        )

        # Mock iterdir to raise exception
        with patch.object(
            monitor.input_dir, "iterdir", side_effect=OSError("Permission denied")
        ):
            # Start polling thread
            monitor._stop_event = Event()
            monitor._stop_event.set()  # Stop immediately

            # Should handle error gracefully
            monitor._poll_directory()

    def test_start_existing_files_error(self, tmp_path, mock_transcriber):
        """Test processing existing files with transcription error."""
        # Create existing file
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        test_file = input_dir / "test.mp3"
        test_file.write_text("fake audio")

        # Make transcriber raise error
        mock_transcriber.transcribe_and_save.side_effect = TranscriberError("API error")

        monitor = FolderMonitor(
            input_dir=input_dir,
            output_dir=tmp_path / "output",
            done_dir=tmp_path / "done",
            transcriber=mock_transcriber,
        )

        with patch.object(monitor, "_wait_for_file_stability"):
            monitor._process_existing_files()

        # Should record error for existing file
        assert len(monitor.processed_files) == 1
        assert monitor.processed_files[0].status == "error"
