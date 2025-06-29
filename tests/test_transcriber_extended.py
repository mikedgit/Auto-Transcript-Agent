"""Extended tests for transcriber functionality to improve coverage."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from src.transcriber import AudioTranscriber, TranscriberError


class TestAudioTranscriberExtended:
    """Extended tests for AudioTranscriber class."""

    def test_transcribe_file_empty_text(self, tmp_path):
        """Test transcription returning empty text."""
        test_file = tmp_path / "test.mp3"
        test_file.write_text("fake audio")

        with patch("src.transcriber.aai.Transcriber") as mock_transcriber_class:
            mock_transcript = Mock()
            mock_transcript.status = "completed"
            mock_transcript.text = ""  # Empty text

            mock_transcriber_instance = Mock()
            mock_transcriber_instance.transcribe.return_value = mock_transcript
            mock_transcriber_class.return_value = mock_transcriber_instance

            transcriber = AudioTranscriber(api_key="valid_key")
            transcriber.transcriber = mock_transcriber_instance

            result = transcriber.transcribe_file(test_file)

            assert result == ""

    @patch("src.transcriber.time.sleep")
    @patch("src.transcriber.aai.Transcriber")
    def test_transcribe_file_retry_success(
        self, mock_transcriber_class, mock_sleep, tmp_path
    ):
        """Test transcription succeeding after retries."""
        test_file = tmp_path / "test.mp3"
        test_file.write_text("fake audio")

        # First call fails, second succeeds
        mock_transcript_error = Mock()
        mock_transcript_error.status = "error"
        mock_transcript_error.error = "Temporary error"

        mock_transcript_success = Mock()
        mock_transcript_success.status = "completed"
        mock_transcript_success.text = "Success!"

        mock_transcriber_instance = Mock()
        mock_transcriber_instance.transcribe.side_effect = [
            mock_transcript_error,
            mock_transcript_success,
        ]
        mock_transcriber_class.return_value = mock_transcriber_instance

        transcriber = AudioTranscriber(
            api_key="valid_key", max_retries=2, retry_delay=1
        )
        transcriber.transcriber = mock_transcriber_instance

        result = transcriber.transcribe_file(test_file)

        assert result == "Success!"
        assert mock_sleep.call_count == 1  # Should have slept between retries

    @patch("src.transcriber.time.sleep")
    @patch("src.transcriber.aai.Transcriber")
    def test_transcribe_file_generic_exception_retry(
        self, mock_transcriber_class, mock_sleep, tmp_path
    ):
        """Test transcription with generic exception and retry."""
        test_file = tmp_path / "test.mp3"
        test_file.write_text("fake audio")

        mock_transcriber_instance = Mock()
        mock_transcriber_instance.transcribe.side_effect = [
            Exception("Network error"),
            Exception("Another error"),
        ]
        mock_transcriber_class.return_value = mock_transcriber_instance

        transcriber = AudioTranscriber(
            api_key="valid_key", max_retries=2, retry_delay=1
        )
        transcriber.transcriber = mock_transcriber_instance

        with pytest.raises(
            TranscriberError, match="Transcription failed after 2 attempts"
        ):
            transcriber.transcribe_file(test_file)

        assert mock_sleep.call_count == 1  # Should have slept between retries

    def test_save_transcript_directory_creation_error(self, tmp_path):
        """Test save transcript with directory creation error."""
        transcriber = AudioTranscriber(api_key="valid_key")

        # Try to save to a path that can't be created
        output_path = Path("/root/restricted/transcript.txt")

        with pytest.raises(TranscriberError, match="Failed to save transcript"):
            transcriber.save_transcript("test transcript", output_path)

    def test_save_transcript_write_error(self, tmp_path):
        """Test save transcript with file write error."""
        transcriber = AudioTranscriber(api_key="valid_key")

        output_path = tmp_path / "transcript.txt"

        # Mock open to raise exception
        with patch("builtins.open", side_effect=OSError("Permission denied")):
            with pytest.raises(TranscriberError, match="Failed to save transcript"):
                transcriber.save_transcript("test transcript", output_path)

    def test_get_transcription_info_nonexistent_file(self):
        """Test getting info for non-existent file."""
        transcriber = AudioTranscriber(api_key="valid_key")

        nonexistent_file = Path("/tmp/nonexistent.mp3")
        info = transcriber.get_transcription_info(nonexistent_file)

        assert info["file_path"] == str(nonexistent_file)
        assert info["file_size"] == 0
        assert info["supported"] is True  # Based on extension
        assert info["extension"] == ".mp3"

    @patch("src.transcriber.aai.Transcriber")
    def test_transcribe_and_save_save_error(self, mock_transcriber_class, tmp_path):
        """Test transcribe_and_save with save error."""
        input_file = tmp_path / "input.mp3"
        input_file.write_text("fake audio")

        mock_transcript = Mock()
        mock_transcript.status = "completed"
        mock_transcript.text = "Transcribed text"

        mock_transcriber_instance = Mock()
        mock_transcriber_instance.transcribe.return_value = mock_transcript
        mock_transcriber_class.return_value = mock_transcriber_instance

        transcriber = AudioTranscriber(api_key="valid_key")
        transcriber.transcriber = mock_transcriber_instance

        # Mock save_transcript to raise error
        with patch.object(
            transcriber, "save_transcript", side_effect=TranscriberError("Save failed")
        ):
            output_file = tmp_path / "output.txt"

            with pytest.raises(TranscriberError, match="Save failed"):
                transcriber.transcribe_and_save(input_file, output_file)

    def test_init_speech_model_configuration(self):
        """Test initialization with different speech models."""
        # Test both valid models
        transcriber_best = AudioTranscriber(api_key="valid_key", speech_model="best")
        transcriber_nano = AudioTranscriber(api_key="valid_key", speech_model="nano")

        # Both should initialize successfully
        assert transcriber_best.max_retries == 3
        assert transcriber_nano.max_retries == 3

    def test_supported_extensions_case_insensitive(self):
        """Test that file extension checking is case insensitive."""
        transcriber = AudioTranscriber(api_key="valid_key")

        # Test various cases
        assert transcriber.is_supported_file(Path("test.MP3"))
        assert transcriber.is_supported_file(Path("test.WaV"))
        assert transcriber.is_supported_file(Path("test.M4A"))
        assert transcriber.is_supported_file(Path("test.FLAC"))

    @patch("src.transcriber.aai.Transcriber")
    def test_transcribe_file_logging(self, mock_transcriber_class, tmp_path, caplog):
        """Test that transcription logs appropriately."""
        test_file = tmp_path / "test.mp3"
        test_file.write_text("fake audio")

        mock_transcript = Mock()
        mock_transcript.status = "completed"
        mock_transcript.text = "Transcribed text with some length"

        mock_transcriber_instance = Mock()
        mock_transcriber_instance.transcribe.return_value = mock_transcript
        mock_transcriber_class.return_value = mock_transcriber_instance

        transcriber = AudioTranscriber(api_key="valid_key")
        transcriber.transcriber = mock_transcriber_instance

        with caplog.at_level("INFO"):
            transcriber.transcribe_file(test_file)

        # Check that appropriate log messages were generated
        assert "Starting transcription" in caplog.text
        assert "Successfully transcribed" in caplog.text
        assert "characters" in caplog.text

    def test_transcribe_file_various_extensions(self, tmp_path):
        """Test transcription with various supported file extensions."""
        transcriber = AudioTranscriber(api_key="valid_key")

        extensions = [".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg", ".webm"]

        for ext in extensions:
            test_file = tmp_path / f"test{ext}"
            test_file.write_text("fake audio")

            # Should recognize as supported
            assert transcriber.is_supported_file(test_file)

            # Test getting info
            info = transcriber.get_transcription_info(test_file)
            assert info["supported"] is True
            assert info["extension"] == ext
