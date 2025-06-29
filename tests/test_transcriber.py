"""Tests for the AudioTranscriber class."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from src.transcriber import AudioTranscriber, TranscriberError


class TestAudioTranscriber:
    """Test the AudioTranscriber class."""

    def test_init_valid_api_key(self):
        """Test initializing with a valid API key."""
        transcriber = AudioTranscriber(api_key="valid_key_123")

        assert transcriber.max_retries == 3  # default
        assert transcriber.retry_delay == 60  # default

    def test_init_invalid_api_key(self):
        """Test that invalid API keys are rejected."""
        with pytest.raises(
            TranscriberError, match="Valid AssemblyAI API key is required"
        ):
            AudioTranscriber(api_key="your_api_key_here")

        with pytest.raises(
            TranscriberError, match="Valid AssemblyAI API key is required"
        ):
            AudioTranscriber(api_key="")

    def test_init_invalid_speech_model(self):
        """Test that invalid speech models are rejected."""
        with pytest.raises(TranscriberError, match="Unsupported speech model"):
            AudioTranscriber(api_key="valid_key", speech_model="invalid_model")

    def test_init_with_options(self):
        """Test initialization with custom options."""
        transcriber = AudioTranscriber(
            api_key="valid_key", speech_model="nano", max_retries=5, retry_delay=30
        )

        assert transcriber.max_retries == 5
        assert transcriber.retry_delay == 30

    def test_is_supported_file(self):
        """Test checking if file formats are supported."""
        transcriber = AudioTranscriber(api_key="valid_key")

        # Supported formats
        assert transcriber.is_supported_file(Path("test.mp3"))
        assert transcriber.is_supported_file(Path("test.wav"))
        assert transcriber.is_supported_file(Path("test.m4a"))
        assert transcriber.is_supported_file(Path("test.flac"))
        assert transcriber.is_supported_file(Path("TEST.MP3"))  # Case insensitive

        # Unsupported formats
        assert not transcriber.is_supported_file(Path("test.txt"))
        assert not transcriber.is_supported_file(Path("test.pdf"))
        assert not transcriber.is_supported_file(Path("test"))  # No extension

    def test_get_transcription_info(self, tmp_path):
        """Test getting transcription info for a file."""
        transcriber = AudioTranscriber(api_key="valid_key")

        # Create a test file
        test_file = tmp_path / "test.mp3"
        test_file.write_text("fake audio data")

        info = transcriber.get_transcription_info(test_file)

        assert info["file_path"] == str(test_file)
        assert info["file_size"] > 0
        assert info["supported"] is True
        assert info["extension"] == ".mp3"

        # Test with unsupported file
        unsupported_file = tmp_path / "test.txt"
        info = transcriber.get_transcription_info(unsupported_file)
        assert info["supported"] is False

    def test_save_transcript(self, tmp_path):
        """Test saving transcript to file."""
        transcriber = AudioTranscriber(api_key="valid_key")

        output_file = tmp_path / "output" / "transcript.txt"
        transcript_text = "This is a test transcript."

        transcriber.save_transcript(transcript_text, output_file)

        assert output_file.exists()
        assert output_file.read_text() == transcript_text

    def test_save_transcript_creates_directory(self, tmp_path):
        """Test that save_transcript creates the output directory if it doesn't exist."""
        transcriber = AudioTranscriber(api_key="valid_key")

        # Directory doesn't exist yet
        output_file = tmp_path / "nonexistent" / "dir" / "transcript.txt"
        transcript_text = "Test transcript"

        transcriber.save_transcript(transcript_text, output_file)

        assert output_file.exists()
        assert output_file.read_text() == transcript_text

    @patch("src.transcriber.aai.Transcriber")
    def test_transcribe_file_success(self, mock_transcriber_class, tmp_path):
        """Test successful file transcription."""
        # Create a test audio file
        test_file = tmp_path / "test.mp3"
        test_file.write_text("fake audio data")

        # Mock the transcription result
        mock_transcript = Mock()
        mock_transcript.status = "completed"
        mock_transcript.text = "This is the transcribed text."
        mock_transcript.error = None

        mock_transcriber_instance = Mock()
        mock_transcriber_instance.transcribe.return_value = mock_transcript
        mock_transcriber_class.return_value = mock_transcriber_instance

        transcriber = AudioTranscriber(api_key="valid_key")
        transcriber.transcriber = mock_transcriber_instance

        result = transcriber.transcribe_file(test_file)

        assert result == "This is the transcribed text."
        mock_transcriber_instance.transcribe.assert_called_once_with(str(test_file))

    @patch("src.transcriber.aai.Transcriber")
    def test_transcribe_file_error(self, mock_transcriber_class, tmp_path):
        """Test transcription error handling."""
        test_file = tmp_path / "test.mp3"
        test_file.write_text("fake audio data")

        # Mock error response
        mock_transcript = Mock()
        mock_transcript.status = "error"
        mock_transcript.error = "API quota exceeded"

        mock_transcriber_instance = Mock()
        mock_transcriber_instance.transcribe.return_value = mock_transcript
        mock_transcriber_class.return_value = mock_transcriber_instance

        transcriber = AudioTranscriber(api_key="valid_key", max_retries=1)
        transcriber.transcriber = mock_transcriber_instance

        with pytest.raises(TranscriberError, match="Transcription failed"):
            transcriber.transcribe_file(test_file)

    def test_transcribe_file_nonexistent(self):
        """Test transcribing a file that doesn't exist."""
        transcriber = AudioTranscriber(api_key="valid_key")
        nonexistent_file = Path("/tmp/nonexistent.mp3")

        with pytest.raises(TranscriberError, match="Audio file does not exist"):
            transcriber.transcribe_file(nonexistent_file)

    def test_transcribe_unsupported_format(self, tmp_path):
        """Test transcribing an unsupported file format."""
        transcriber = AudioTranscriber(api_key="valid_key")

        unsupported_file = tmp_path / "test.txt"
        unsupported_file.write_text("This is not audio")

        with pytest.raises(TranscriberError, match="Unsupported file format"):
            transcriber.transcribe_file(unsupported_file)

    @patch("src.transcriber.aai.Transcriber")
    def test_transcribe_and_save_success(self, mock_transcriber_class, tmp_path):
        """Test successful transcribe and save operation."""
        # Setup
        input_file = tmp_path / "input.mp3"
        input_file.write_text("fake audio")
        output_file = tmp_path / "output.txt"

        mock_transcript = Mock()
        mock_transcript.status = "completed"
        mock_transcript.text = "Transcribed text"

        mock_transcriber_instance = Mock()
        mock_transcriber_instance.transcribe.return_value = mock_transcript
        mock_transcriber_class.return_value = mock_transcriber_instance

        transcriber = AudioTranscriber(api_key="valid_key")
        transcriber.transcriber = mock_transcriber_instance

        # Execute
        result = transcriber.transcribe_and_save(input_file, output_file)

        # Verify
        assert result["status"] == "success"
        assert result["input_file"] == str(input_file)
        assert result["output_file"] == str(output_file)
        assert result["transcript_length"] == len("Transcribed text")
        assert result["error"] is None
        assert output_file.exists()
        assert output_file.read_text() == "Transcribed text"

    @patch("src.transcriber.aai.Transcriber")
    def test_transcribe_and_save_error(self, mock_transcriber_class, tmp_path):
        """Test transcribe and save with error."""
        input_file = tmp_path / "input.mp3"
        input_file.write_text("fake audio")
        output_file = tmp_path / "output.txt"

        mock_transcriber_instance = Mock()
        mock_transcriber_instance.transcribe.side_effect = Exception("API Error")
        mock_transcriber_class.return_value = mock_transcriber_instance

        transcriber = AudioTranscriber(api_key="valid_key", max_retries=1)
        transcriber.transcriber = mock_transcriber_instance

        with pytest.raises(TranscriberError):
            transcriber.transcribe_and_save(input_file, output_file)
