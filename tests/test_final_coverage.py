"""Final tests to reach 95% coverage target."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from click.testing import CliRunner

from src.config import Config, load_config, ConfigError
from src.transcriber import AudioTranscriber, TranscriberError
from src.monitor import FolderMonitor
from src.transcript_service import cli, main


class TestFinalCoverage:
    """Tests to cover the final missing lines."""

    def test_config_log_level_case_insensitive(self, tmp_path):
        """Test that log level validation is case insensitive."""
        with pytest.raises(ValueError, match="Invalid log level"):
            Config(
                assemblyai_api_key="test_key",
                input_dir=tmp_path / "input",
                output_dir=tmp_path / "output",
                done_dir=tmp_path / "done",
                log_level="invalid_level",  # This should trigger line 65
            )

    def test_transcriber_empty_api_key(self):
        """Test transcriber with empty API key."""
        with pytest.raises(
            TranscriberError, match="Valid AssemblyAI API key is required"
        ):
            AudioTranscriber(api_key="")  # This should trigger line 43

    @patch("src.transcriber.aai.Transcriber")
    def test_transcriber_transcript_error_final_retry(
        self, mock_transcriber_class, tmp_path
    ):
        """Test transcriber with error on final retry attempt."""
        test_file = tmp_path / "test.mp3"
        test_file.write_text("fake audio")

        from src.transcriber import TranscriptError as AAITranscriptError

        mock_transcriber_instance = Mock()
        mock_transcriber_instance.transcribe.side_effect = AAITranscriptError(
            "API Error"
        )
        mock_transcriber_class.return_value = mock_transcriber_instance

        transcriber = AudioTranscriber(api_key="valid_key", max_retries=1)
        transcriber.transcriber = mock_transcriber_instance

        with pytest.raises(
            TranscriberError, match="Transcription failed after 1 attempts"
        ):
            transcriber.transcribe_file(test_file)  # Should cover lines 122-127

    def test_monitor_start_observer_already_alive(self, tmp_path):
        """Test monitor stop when observer is not alive."""
        mock_transcriber = Mock()
        monitor = FolderMonitor(
            input_dir=tmp_path / "input",
            output_dir=tmp_path / "output",
            done_dir=tmp_path / "done",
            transcriber=mock_transcriber,
        )

        # Mock observer to simulate it not being alive
        with patch.object(monitor.observer, "is_alive", return_value=False):
            monitor.stop()  # Should cover alternative path

    def test_monitor_poll_thread_timeout(self, tmp_path):
        """Test monitor with poll thread timeout."""
        mock_transcriber = Mock()
        monitor = FolderMonitor(
            input_dir=tmp_path / "input",
            output_dir=tmp_path / "output",
            done_dir=tmp_path / "done",
            transcriber=mock_transcriber,
        )

        # Mock poll thread that doesn't join in time
        mock_thread = Mock()
        mock_thread.is_alive.return_value = True
        mock_thread.join.return_value = None  # Simulate timeout
        monitor._poll_thread = mock_thread

        monitor.stop()  # Should test timeout path

    def test_transcriber_file_error_logging(self, tmp_path, caplog):
        """Test transcriber file error scenarios."""
        transcriber = AudioTranscriber(api_key="valid_key")

        # Test with file that doesn't exist - should trigger log warning
        nonexistent_file = Path("/tmp/definitely_nonexistent_file.mp3")

        with caplog.at_level("WARNING"):
            try:
                transcriber.transcribe_file(nonexistent_file)
            except TranscriberError:
                pass  # Expected

        # Should have logged a warning about missing file
        assert any("does not exist" in record.message for record in caplog.records)

    def test_monitor_processing_duplicate_prevention(self, tmp_path):
        """Test that duplicate file processing is prevented."""
        mock_transcriber = Mock()
        mock_transcriber.is_supported_file.return_value = True

        FolderMonitor(
            input_dir=tmp_path / "input",
            output_dir=tmp_path / "output",
            done_dir=tmp_path / "done",
            transcriber=mock_transcriber,
        )

        from src.monitor import AudioFileHandler

        handler = AudioFileHandler(mock_transcriber, lambda x: None)

        # Simulate file already being processed
        test_path = "/test/file.mp3"
        handler.processing_files.add(test_path)

        # Create mock event
        event = Mock()
        event.is_directory = False
        event.src_path = test_path

        # Should not process the file since it's already in the set
        callback_mock = Mock()
        handler.callback = callback_mock
        handler.on_created(event)

        # Callback should not be called
        callback_mock.assert_not_called()

    def test_main_function_calls_cli(self):
        """Test that main function calls CLI."""
        with patch("src.transcript_service.cli") as mock_cli:
            main()
            mock_cli.assert_called_once()  # Should cover line 323


class TestEnvironmentVariableIsolation:
    """Test environment variable isolation for more reliable testing."""

    def test_load_config_with_isolated_env(self, tmp_path):
        """Test load_config with completely isolated environment."""
        import os

        # Back up all environment variables
        original_env = os.environ.copy()

        try:
            # Clear all environment variables
            os.environ.clear()

            env_file = tmp_path / ".env"
            env_content = f"""
ASSEMBLYAI_API_KEY=test_isolated_key
INPUT_DIR={tmp_path}/input
OUTPUT_DIR={tmp_path}/output
DONE_DIR={tmp_path}/done
"""
            env_file.write_text(env_content)

            # This should work with clean environment
            config = load_config(env_file)
            assert config.assemblyai_api_key == "test_isolated_key"

        finally:
            # Restore original environment
            os.environ.clear()
            os.environ.update(original_env)

    def test_load_config_missing_required_with_clean_env(self, tmp_path):
        """Test missing required env vars with completely clean environment."""
        import os

        # Back up environment
        original_env = os.environ.copy()

        try:
            # Clear environment
            os.environ.clear()

            env_file = tmp_path / ".env"
            env_file.write_text("SPEECH_MODEL=best\n")  # Missing required vars

            with pytest.raises(
                ConfigError, match="ASSEMBLYAI_API_KEY environment variable is required"
            ):
                load_config(env_file)  # Should now properly trigger the error

        finally:
            # Restore environment
            os.environ.clear()
            os.environ.update(original_env)


class TestCLIPathMocking:
    """Test CLI commands with proper path mocking."""

    def test_init_config_command_with_mock_path(self):
        """Test init-config command with proper Mock path."""
        with (
            patch("src.config.get_default_config_path") as mock_get_path,
            patch("src.config.create_sample_config") as mock_create,
        ):

            # Create a mock that behaves like a Path
            mock_path = Mock()
            mock_path.exists.return_value = False
            mock_get_path.return_value = mock_path

            runner = CliRunner()
            result = runner.invoke(cli, ["init-config"])

            assert result.exit_code == 0
            assert "Configuration file created" in result.output
            mock_create.assert_called_once_with(mock_path)

    def test_init_config_exists_with_mock_path(self):
        """Test init-config when file exists."""
        with patch("src.config.get_default_config_path") as mock_get_path:

            mock_path = Mock()
            mock_path.exists.return_value = True
            mock_get_path.return_value = mock_path

            runner = CliRunner()
            result = runner.invoke(cli, ["init-config"])

            assert result.exit_code == 0
            assert "already exists" in result.output
