"""Tests for the main transcript service."""

import pytest
from unittest.mock import Mock, patch

from src.transcript_service import TranscriptService
from src.config import ConfigError


class TestTranscriptService:
    """Test the TranscriptService class."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """Create a mock configuration for testing."""
        mock_config = Mock()
        mock_config.assemblyai_api_key = "test_api_key"
        mock_config.speech_model = "best"
        mock_config.input_dir = tmp_path / "input"
        mock_config.output_dir = tmp_path / "output"
        mock_config.done_dir = tmp_path / "done"
        mock_config.poll_interval = 5
        mock_config.max_retries = 3
        mock_config.retry_delay = 60
        mock_config.log_level = "INFO"
        mock_config.log_file = None
        return mock_config

    @patch("src.transcript_service.load_config")
    @patch("src.transcript_service.setup_logging")
    def test_init_success(self, mock_setup_logging, mock_load_config, mock_config):
        """Test successful service initialization."""
        mock_load_config.return_value = mock_config

        service = TranscriptService()

        assert service.config == mock_config
        assert service.transcriber is None
        assert service.monitor is None
        assert service.running is False

        mock_load_config.assert_called_once_with(None)
        mock_setup_logging.assert_called_once_with(mock_config)

    @patch("src.transcript_service.load_config")
    def test_init_config_error(self, mock_load_config):
        """Test initialization with configuration error."""
        mock_load_config.side_effect = ConfigError("Invalid config")

        with pytest.raises(SystemExit):
            TranscriptService()

    @patch("src.transcript_service.load_config")
    @patch("src.transcript_service.setup_logging")
    @patch("src.transcript_service.validate_directories")
    @patch("src.transcript_service.AudioTranscriber")
    @patch("src.transcript_service.FolderMonitor")
    def test_start_success(
        self,
        mock_monitor_class,
        mock_transcriber_class,
        mock_validate_dirs,
        mock_setup_logging,
        mock_load_config,
        mock_config,
    ):
        """Test successful service startup."""
        mock_load_config.return_value = mock_config
        mock_transcriber = Mock()
        mock_monitor = Mock()
        mock_transcriber_class.return_value = mock_transcriber
        mock_monitor_class.return_value = mock_monitor

        service = TranscriptService()
        service.start()

        assert service.running is True
        assert service.transcriber == mock_transcriber
        assert service.monitor == mock_monitor

        mock_validate_dirs.assert_called_once_with(mock_config)
        mock_transcriber_class.assert_called_once_with(
            api_key="test_api_key", speech_model="best", max_retries=3, retry_delay=60
        )
        mock_monitor.start.assert_called_once()

    @patch("src.transcript_service.load_config")
    @patch("src.transcript_service.setup_logging")
    def test_start_already_running(
        self, mock_setup_logging, mock_load_config, mock_config
    ):
        """Test starting service when already running."""
        mock_load_config.return_value = mock_config

        service = TranscriptService()
        service.running = True

        # Should return early without doing anything
        service.start()

        assert service.transcriber is None
        assert service.monitor is None

    @patch("src.transcript_service.load_config")
    @patch("src.transcript_service.setup_logging")
    def test_stop(self, mock_setup_logging, mock_load_config, mock_config):
        """Test stopping the service."""
        mock_load_config.return_value = mock_config

        service = TranscriptService()
        service.running = True
        service.monitor = Mock()

        service.stop()

        assert service.running is False
        service.monitor.stop.assert_called_once()

    @patch("src.transcript_service.load_config")
    @patch("src.transcript_service.setup_logging")
    def test_stop_not_running(self, mock_setup_logging, mock_load_config, mock_config):
        """Test stopping service when not running."""
        mock_load_config.return_value = mock_config

        service = TranscriptService()
        service.monitor = Mock()

        # Should return early
        service.stop()

        service.monitor.stop.assert_not_called()

    @patch("src.transcript_service.load_config")
    @patch("src.transcript_service.setup_logging")
    def test_get_status(self, mock_setup_logging, mock_load_config, mock_config):
        """Test getting service status."""
        mock_load_config.return_value = mock_config

        service = TranscriptService()
        service.running = True
        service.transcriber = Mock()
        service.monitor = Mock()
        service.monitor.observer.is_alive.return_value = True
        service.monitor.get_statistics.return_value = {
            "total_processed": 10,
            "successful": 8,
            "errors": 2,
        }
        service.monitor.get_recent_files.return_value = []

        status = service.get_status()

        assert status["running"] is True
        assert status["config_loaded"] is True
        assert status["transcriber_initialized"] is True
        assert status["monitor_active"] is True
        assert "directories" in status
        assert "statistics" in status
        assert "recent_files" in status

    @patch("src.transcript_service.load_config")
    @patch("src.transcript_service.setup_logging")
    @patch("src.transcript_service.signal.signal")
    @patch("src.transcript_service.time.sleep")
    def test_run_keyboard_interrupt(
        self, mock_sleep, mock_signal, mock_setup_logging, mock_load_config, mock_config
    ):
        """Test running service with keyboard interrupt."""
        mock_load_config.return_value = mock_config
        mock_sleep.side_effect = KeyboardInterrupt()

        service = TranscriptService()
        service.start = Mock()
        service.stop = Mock()

        service.run()

        service.start.assert_called_once()
        service.stop.assert_called_once()

    @patch("src.transcript_service.load_config")
    @patch("src.transcript_service.setup_logging")
    def test_signal_handler(self, mock_setup_logging, mock_load_config, mock_config):
        """Test signal handler for graceful shutdown."""
        import signal

        mock_load_config.return_value = mock_config

        service = TranscriptService()
        service.running = True

        # Simulate receiving SIGTERM
        service._signal_handler(signal.SIGTERM, None)

        assert service.running is False

    @patch("src.transcript_service.load_config")
    @patch("src.transcript_service.setup_logging")
    def test_log_statistics(self, mock_setup_logging, mock_load_config, mock_config):
        """Test logging service statistics."""
        mock_load_config.return_value = mock_config

        service = TranscriptService()
        service.monitor = Mock()
        service.monitor.get_statistics.return_value = {
            "total_processed": 5,
            "successful": 4,
            "errors": 1,
        }

        # Should not raise an exception
        service._log_statistics()

        service.monitor.get_statistics.assert_called_once()
        assert hasattr(service, "_last_stats_time")
