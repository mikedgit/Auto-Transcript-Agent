"""Focused tests to achieve 95% coverage on missing lines."""

import pytest
import os
from pathlib import Path
from unittest.mock import Mock, patch
from click.testing import CliRunner

from src.config import load_config, ConfigError, validate_directories
from src.transcriber import AudioTranscriber
from src.monitor import FolderMonitor
from src.transcript_service import TranscriptService, cli


class TestCoverageFocused:
    """Tests specifically designed to cover missing lines."""

    def test_load_config_integer_conversion_error(self, tmp_path):
        """Test load_config with integer conversion errors."""
        env_file = tmp_path / ".env"
        env_content = f"""
ASSEMBLYAI_API_KEY=test_key
INPUT_DIR={tmp_path}/input
OUTPUT_DIR={tmp_path}/output
DONE_DIR={tmp_path}/done
POLL_INTERVAL=not_a_number
"""
        env_file.write_text(env_content)

        with pytest.raises(ConfigError, match="Failed to load configuration"):
            load_config(env_file)

    def test_validate_directories_permission_error(self, tmp_path):
        """Test validate_directories with permission errors."""
        from src.config import Config

        config = Config(
            assemblyai_api_key="test_key",
            input_dir=tmp_path / "input",
            output_dir=tmp_path / "output",
            done_dir=tmp_path / "done",
        )

        # Create input directory but make it non-readable
        config.input_dir.mkdir()

        with patch("os.access", return_value=False):
            with pytest.raises(ConfigError, match="Directory validation failed"):
                validate_directories(config)

    def test_validate_directories_creation_error(self, tmp_path):
        """Test validate_directories with directory creation errors."""
        from src.config import Config

        config = Config(
            assemblyai_api_key="test_key",
            input_dir=tmp_path / "input",
            output_dir=tmp_path / "output",
            done_dir=tmp_path / "done",
        )

        # Mock mkdir to raise exception for output directory
        original_mkdir = Path.mkdir

        def mock_mkdir(self, parents=False, exist_ok=False):
            if "output" in str(self):
                raise OSError("Permission denied")
            return original_mkdir(self, parents=parents, exist_ok=exist_ok)

        with patch.object(Path, "mkdir", side_effect=mock_mkdir):
            with pytest.raises(ConfigError, match="Cannot access output directory"):
                validate_directories(config)

    @patch("src.transcriber.time.sleep")
    @patch("src.transcriber.aai.Transcriber")
    def test_transcriber_multiple_retries(
        self, mock_transcriber_class, mock_sleep, tmp_path
    ):
        """Test transcriber with multiple retry attempts."""
        test_file = tmp_path / "test.mp3"
        test_file.write_text("fake audio")

        mock_transcriber_instance = Mock()

        # First two calls fail, third succeeds
        error_transcript = Mock()
        error_transcript.status = "error"
        error_transcript.error = "Rate limit"

        success_transcript = Mock()
        success_transcript.status = "completed"
        success_transcript.text = "Success after retries"

        mock_transcriber_instance.transcribe.side_effect = [
            error_transcript,
            error_transcript,
            success_transcript,
        ]
        mock_transcriber_class.return_value = mock_transcriber_instance

        transcriber = AudioTranscriber(
            api_key="valid_key", max_retries=3, retry_delay=1
        )
        transcriber.transcriber = mock_transcriber_instance

        result = transcriber.transcribe_file(test_file)
        assert result == "Success after retries"
        assert mock_sleep.call_count == 2  # Two retries

    def test_monitor_start_stop_with_threads(self, tmp_path):
        """Test monitor start/stop with actual thread handling."""
        mock_transcriber = Mock()
        mock_transcriber.is_supported_file.return_value = True

        monitor = FolderMonitor(
            input_dir=tmp_path / "input",
            output_dir=tmp_path / "output",
            done_dir=tmp_path / "done",
            transcriber=mock_transcriber,
        )

        # Start and immediately stop to test thread lifecycle
        with (
            patch.object(monitor.observer, "start"),
            patch.object(monitor.observer, "stop"),
            patch.object(monitor.observer, "join"),
            patch.object(monitor.observer, "is_alive", return_value=True),
        ):

            monitor.start()
            assert monitor._poll_thread is not None

            monitor.stop()

    def test_monitor_poll_directory_with_files(self, tmp_path):
        """Test polling directory functionality."""
        mock_transcriber = Mock()
        mock_transcriber.is_supported_file.return_value = True

        monitor = FolderMonitor(
            input_dir=tmp_path / "input",
            output_dir=tmp_path / "output",
            done_dir=tmp_path / "done",
            transcriber=mock_transcriber,
            poll_interval=0.1,
        )

        # Create a test file
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        test_file = input_dir / "test.mp3"
        test_file.write_text("fake audio")

        # Mock the process file method
        with (
            patch.object(monitor, "_process_file") as mock_process,
            patch.object(monitor, "_is_recently_processed", return_value=False),
        ):

            # Set stop event immediately
            monitor._stop_event.set()
            monitor._poll_directory()

            # Should have tried to process the file
            mock_process.assert_called()

    @patch("src.transcript_service.signal.signal")
    @patch("src.transcript_service.time.sleep")
    def test_service_run_with_statistics_timing(
        self, mock_sleep, mock_signal, tmp_path
    ):
        """Test service run with statistics logging timing."""
        with (
            patch("src.transcript_service.load_config") as mock_load_config,
            patch("src.transcript_service.setup_logging"),
        ):

            mock_config = Mock()
            mock_config.input_dir = tmp_path / "input"
            mock_config.output_dir = tmp_path / "output"
            mock_config.done_dir = tmp_path / "done"
            mock_load_config.return_value = mock_config

            service = TranscriptService()
            service.start = Mock()
            service.stop = Mock()
            service.monitor = Mock()
            service.monitor.get_statistics.return_value = {"test": "stats"}

            # Set statistics time to trigger logging
            import time

            service._last_stats_time = time.time() - 3700  # Over an hour ago

            # Make sleep trigger statistics logging then exit
            call_count = [0]

            def mock_sleep_side_effect(duration):
                call_count[0] += 1
                if call_count[0] == 1:
                    return  # First call - allow statistics
                raise KeyboardInterrupt()  # Second call - exit

            mock_sleep.side_effect = mock_sleep_side_effect

            service.run()

            # Should have called get_statistics
            service.monitor.get_statistics.assert_called()

    def test_cli_transcribe_no_transcriber_init(self, tmp_path):
        """Test CLI transcribe when transcriber needs initialization."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_text("fake audio")

        with patch("src.transcript_service.TranscriptService") as mock_service_class:
            mock_service = Mock()
            mock_service.transcriber = None  # Not initialized
            mock_service.config = Mock()
            mock_service.config.assemblyai_api_key = "test_key"
            mock_service.config.speech_model = "best"
            mock_service.config.max_retries = 3
            mock_service.config.retry_delay = 60

            # Mock AudioTranscriber creation
            with patch(
                "src.transcript_service.AudioTranscriber"
            ) as mock_transcriber_class:
                mock_transcriber = Mock()
                mock_transcriber.transcribe_and_save.return_value = {
                    "status": "success",
                    "duration_seconds": 2.5,
                    "transcript_length": 75,
                    "output_file": str(tmp_path / "test.txt"),
                }
                mock_transcriber_class.return_value = mock_transcriber
                mock_service_class.return_value = mock_service

                runner = CliRunner()
                result = runner.invoke(cli, ["transcribe", str(audio_file)])

                assert result.exit_code == 0
                # Should have initialized the transcriber
                mock_transcriber_class.assert_called_once()

    def test_monitor_file_stability_exception_handling(self, tmp_path):
        """Test file stability checking with exceptions."""
        mock_transcriber = Mock()
        monitor = FolderMonitor(
            input_dir=tmp_path / "input",
            output_dir=tmp_path / "output",
            done_dir=tmp_path / "done",
            transcriber=mock_transcriber,
        )

        test_file = tmp_path / "test.mp3"
        test_file.write_text("initial content")

        # Mock stat to raise an exception after a few calls
        call_count = [0]

        def mock_stat():
            call_count[0] += 1
            if call_count[0] < 3:
                mock_result = Mock()
                mock_result.st_size = 100
                return mock_result
            else:
                raise OSError("Stat failed")

        with (
            patch.object(test_file, "stat", side_effect=mock_stat),
            patch("src.monitor.time.sleep"),
        ):

            # Should handle the exception gracefully
            monitor._wait_for_file_stability(test_file, max_wait=2)


class TestSecurityFocused:
    """Security-focused tests."""

    def test_api_key_not_logged(self, tmp_path, caplog):
        """Test that API keys are not logged in plain text."""
        from src.config import Config, setup_logging

        config = Config(
            assemblyai_api_key="secret_api_key_12345",
            input_dir=tmp_path / "input",
            output_dir=tmp_path / "output",
            done_dir=tmp_path / "done",
            log_level="DEBUG",
        )

        with caplog.at_level("DEBUG"):
            setup_logging(config)

        # Check that API key is not in logs
        log_text = caplog.text
        assert "secret_api_key_12345" not in log_text
        assert "***REDACTED***" in log_text or "secret_api_key" not in log_text

    def test_config_to_dict_redacts_api_key(self, tmp_path):
        """Test that config.to_dict() properly redacts the API key."""
        from src.config import Config

        config = Config(
            assemblyai_api_key="secret_api_key_12345",
            input_dir=tmp_path / "input",
            output_dir=tmp_path / "output",
            done_dir=tmp_path / "done",
        )

        config_dict = config.to_dict()
        assert config_dict["assemblyai_api_key"] == "***REDACTED***"
        assert "secret_api_key_12345" not in str(config_dict)

    def test_file_permissions_respected(self, tmp_path):
        """Test that file permissions are checked before operations."""
        from src.config import validate_directories, Config

        # Create directory with restricted permissions
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        config = Config(
            assemblyai_api_key="test_key",
            input_dir=input_dir,
            output_dir=tmp_path / "output",
            done_dir=tmp_path / "done",
        )

        # Mock os.access to return False for input directory
        with patch("os.access") as mock_access:

            def access_side_effect(path, mode):
                if "input" in str(path) and mode == os.R_OK:
                    return False
                return True

            mock_access.side_effect = access_side_effect

            with pytest.raises(ConfigError, match="Input directory is not readable"):
                validate_directories(config)
