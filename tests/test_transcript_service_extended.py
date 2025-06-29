"""Extended tests for transcript service to improve coverage."""

import pytest
import signal
import time
from pathlib import Path
from unittest.mock import Mock, patch
from click.testing import CliRunner

from src.transcript_service import TranscriptService, cli, main


class TestTranscriptServiceExtended:
    """Extended tests for TranscriptService class."""

    def test_init_general_exception(self):
        """Test initialization with general exception."""
        with patch(
            "src.transcript_service.load_config",
            side_effect=RuntimeError("Unexpected error"),
        ):
            with pytest.raises(SystemExit):
                TranscriptService()

    @patch("src.transcript_service.load_config")
    @patch("src.transcript_service.setup_logging")
    @patch("src.transcript_service.validate_directories")
    @patch("src.transcript_service.AudioTranscriber")
    @patch("src.transcript_service.FolderMonitor")
    def test_start_validation_error(
        self,
        mock_monitor_class,
        mock_transcriber_class,
        mock_validate_dirs,
        mock_setup_logging,
        mock_load_config,
    ):
        """Test start with directory validation error."""
        mock_config = Mock()
        mock_load_config.return_value = mock_config
        mock_validate_dirs.side_effect = Exception("Validation failed")

        service = TranscriptService()

        with pytest.raises(Exception, match="Validation failed"):
            service.start()

    @patch("src.transcript_service.load_config")
    @patch("src.transcript_service.setup_logging")
    def test_stop_with_monitor_error(self, mock_setup_logging, mock_load_config):
        """Test stopping service with monitor error."""
        mock_config = Mock()
        mock_load_config.return_value = mock_config

        service = TranscriptService()
        service.running = True
        service.monitor = Mock()
        service.monitor.stop.side_effect = Exception("Stop failed")

        # Should handle error gracefully
        service.stop()
        assert service.running is False

    @patch("src.transcript_service.load_config")
    @patch("src.transcript_service.setup_logging")
    @patch("src.transcript_service.time.sleep")
    def test_run_with_exception(self, mock_sleep, mock_setup_logging, mock_load_config):
        """Test run method with exception during operation."""
        mock_config = Mock()
        mock_load_config.return_value = mock_config

        service = TranscriptService()
        service.start = Mock()
        service.stop = Mock()

        # Make sleep raise exception
        mock_sleep.side_effect = Exception("Unexpected error")

        service.run()

        service.start.assert_called_once()
        service.stop.assert_called_once()

    @patch("src.transcript_service.load_config")
    @patch("src.transcript_service.setup_logging")
    @patch("src.transcript_service.time.sleep")
    def test_run_statistics_logging(
        self, mock_sleep, mock_setup_logging, mock_load_config
    ):
        """Test statistics logging during run."""
        mock_config = Mock()
        mock_load_config.return_value = mock_config

        service = TranscriptService()
        service.start = Mock()
        service.stop = Mock()
        service.monitor = Mock()
        service.monitor.get_statistics.return_value = {"test": "stats"}

        # Simulate time passing for statistics
        service._last_stats_time = time.time() - 3700  # Over an hour ago

        # Make sleep raise KeyboardInterrupt after one iteration
        mock_sleep.side_effect = [None, KeyboardInterrupt()]

        service.run()

        # Should have logged statistics
        service.monitor.get_statistics.assert_called()

    @patch("src.transcript_service.load_config")
    @patch("src.transcript_service.setup_logging")
    def test_get_status_no_monitor(self, mock_setup_logging, mock_load_config):
        """Test get_status when monitor is None."""
        mock_config = Mock()
        mock_config.input_dir = Path("/test/input")
        mock_config.output_dir = Path("/test/output")
        mock_config.done_dir = Path("/test/done")
        mock_load_config.return_value = mock_config

        service = TranscriptService()
        status = service.get_status()

        assert status["running"] is False
        assert status["monitor_active"] is False
        assert "directories" in status


class TestCLICommands:
    """Test CLI command functionality."""

    def test_cli_help(self):
        """Test CLI help command."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "Auto-Transcript-Agent" in result.output
        assert "run" in result.output
        assert "status" in result.output
        assert "transcribe" in result.output

    @patch("src.transcript_service.TranscriptService")
    def test_run_command(self, mock_service_class):
        """Test run command."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service

        runner = CliRunner()
        result = runner.invoke(cli, ["run"])

        assert result.exit_code == 0
        mock_service.run.assert_called_once()

    @patch("src.transcript_service.TranscriptService")
    def test_run_command_keyboard_interrupt(self, mock_service_class):
        """Test run command with keyboard interrupt."""
        mock_service = Mock()
        mock_service.run.side_effect = KeyboardInterrupt()
        mock_service_class.return_value = mock_service

        runner = CliRunner()
        result = runner.invoke(cli, ["run"])

        assert result.exit_code == 0
        assert "interrupted" in result.output

    @patch("src.transcript_service.TranscriptService")
    def test_run_command_exception(self, mock_service_class):
        """Test run command with exception."""
        mock_service = Mock()
        mock_service.run.side_effect = Exception("Service error")
        mock_service_class.return_value = mock_service

        runner = CliRunner()
        result = runner.invoke(cli, ["run"])

        assert result.exit_code == 1
        assert "Service error" in result.output

    @patch("src.transcript_service.TranscriptService")
    def test_status_command(self, mock_service_class):
        """Test status command."""
        mock_service = Mock()
        mock_service.get_status.return_value = {
            "running": True,
            "config_loaded": True,
            "transcriber_initialized": True,
            "monitor_active": True,
            "directories": {
                "input": "/test/input",
                "output": "/test/output",
                "done": "/test/done",
            },
            "statistics": {
                "total_processed": 10,
                "successful": 8,
                "errors": 2,
                "skipped": 0,
                "success_rate": 0.8,
            },
        }
        mock_service_class.return_value = mock_service

        runner = CliRunner()
        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
        assert "Running: True" in result.output
        assert "Total processed: 10" in result.output
        assert "Success rate: 80.0%" in result.output

    @patch("src.transcript_service.TranscriptService")
    def test_status_command_exception(self, mock_service_class):
        """Test status command with exception."""
        mock_service_class.side_effect = Exception("Status error")

        runner = CliRunner()
        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 1
        assert "Status check failed" in result.output

    @patch("src.transcript_service.TranscriptService")
    def test_transcribe_command(self, mock_service_class, tmp_path):
        """Test transcribe command."""
        # Create test audio file
        audio_file = tmp_path / "test.mp3"
        audio_file.write_text("fake audio")

        mock_service = Mock()
        mock_service.transcriber = Mock()
        mock_service.transcriber.transcribe_and_save.return_value = {
            "status": "success",
            "duration_seconds": 5.2,
            "transcript_length": 150,
            "output_file": str(tmp_path / "test.txt"),
        }
        mock_service_class.return_value = mock_service

        runner = CliRunner()
        result = runner.invoke(cli, ["transcribe", str(audio_file)])

        assert result.exit_code == 0
        assert "Transcription completed successfully" in result.output
        assert "Duration: 5.2s" in result.output
        assert "150 characters" in result.output

    @patch("src.transcript_service.TranscriptService")
    def test_transcribe_command_with_output(self, mock_service_class, tmp_path):
        """Test transcribe command with specified output file."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_text("fake audio")
        output_file = tmp_path / "custom_output.txt"

        mock_service = Mock()
        mock_service.transcriber = Mock()
        mock_service.transcriber.transcribe_and_save.return_value = {
            "status": "success",
            "duration_seconds": 3.1,
            "transcript_length": 100,
            "output_file": str(output_file),
        }
        mock_service_class.return_value = mock_service

        runner = CliRunner()
        result = runner.invoke(cli, ["transcribe", str(audio_file), str(output_file)])

        assert result.exit_code == 0
        assert "Transcription completed successfully" in result.output

    @patch("src.transcript_service.TranscriptService")
    def test_transcribe_command_failure(self, mock_service_class, tmp_path):
        """Test transcribe command with failure."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_text("fake audio")

        mock_service = Mock()
        mock_service.transcriber = Mock()
        mock_service.transcriber.transcribe_and_save.return_value = {
            "status": "error",
            "error": "API quota exceeded",
        }
        mock_service_class.return_value = mock_service

        runner = CliRunner()
        result = runner.invoke(cli, ["transcribe", str(audio_file)])

        assert result.exit_code == 1
        assert "Transcription failed" in result.output
        assert "API quota exceeded" in result.output

    @patch("src.transcript_service.TranscriptService")
    def test_transcribe_command_exception(self, mock_service_class, tmp_path):
        """Test transcribe command with exception."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_text("fake audio")

        mock_service_class.side_effect = Exception("Transcribe error")

        runner = CliRunner()
        result = runner.invoke(cli, ["transcribe", str(audio_file)])

        assert result.exit_code == 1
        assert "Transcription failed" in result.output

    @patch("src.config.create_sample_config")
    @patch("src.config.get_default_config_path")
    def test_init_config_command(self, mock_get_path, mock_create_config):
        """Test init-config command."""
        mock_path = Path("/test/.env")
        mock_get_path.return_value = mock_path
        mock_path.exists = Mock(return_value=False)

        runner = CliRunner()
        result = runner.invoke(cli, ["init-config"])

        assert result.exit_code == 0
        assert "Configuration file created" in result.output
        mock_create_config.assert_called_once_with(mock_path)

    @patch("src.config.get_default_config_path")
    def test_init_config_exists_no_force(self, mock_get_path):
        """Test init-config when file exists without force."""
        mock_path = Mock()
        mock_path.exists.return_value = True
        mock_get_path.return_value = mock_path

        runner = CliRunner()
        result = runner.invoke(cli, ["init-config"])

        assert result.exit_code == 0
        assert "already exists" in result.output
        assert "Use --force" in result.output

    @patch("src.config.create_sample_config")
    @patch("src.config.get_default_config_path")
    def test_init_config_force_overwrite(self, mock_get_path, mock_create_config):
        """Test init-config with force overwrite."""
        mock_path = Mock()
        mock_path.exists.return_value = True
        mock_get_path.return_value = mock_path

        runner = CliRunner()
        result = runner.invoke(cli, ["init-config", "--force"])

        assert result.exit_code == 0
        assert "Configuration file created" in result.output
        mock_create_config.assert_called_once_with(mock_path)

    @patch("src.config.create_sample_config")
    @patch("src.config.get_default_config_path")
    def test_init_config_error(self, mock_get_path, mock_create_config):
        """Test init-config with creation error."""
        mock_path = Mock()
        mock_path.exists.return_value = False
        mock_get_path.return_value = mock_path
        mock_create_config.side_effect = Exception("Creation failed")

        runner = CliRunner()
        result = runner.invoke(cli, ["init-config"])

        assert result.exit_code == 1
        assert "Failed to create configuration" in result.output


class TestMainFunction:
    """Test the main entry point function."""

    @patch("src.transcript_service.cli")
    def test_main(self, mock_cli):
        """Test main function calls cli."""
        main()
        mock_cli.assert_called_once()


class TestServiceSignalHandling:
    """Test signal handling in the service."""

    @patch("src.transcript_service.load_config")
    @patch("src.transcript_service.setup_logging")
    def test_signal_handler_sigterm(self, mock_setup_logging, mock_load_config):
        """Test SIGTERM signal handling."""
        mock_config = Mock()
        mock_load_config.return_value = mock_config

        service = TranscriptService()
        service.running = True

        # Test SIGTERM
        service._signal_handler(signal.SIGTERM, None)
        assert service.running is False

    @patch("src.transcript_service.load_config")
    @patch("src.transcript_service.setup_logging")
    def test_signal_handler_unknown(self, mock_setup_logging, mock_load_config):
        """Test unknown signal handling."""
        mock_config = Mock()
        mock_load_config.return_value = mock_config

        service = TranscriptService()
        service.running = True

        # Test unknown signal
        service._signal_handler(999, None)
        assert service.running is False
