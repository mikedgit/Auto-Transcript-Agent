"""AssemblyAI integration for audio transcription."""

import logging
import time
from pathlib import Path
from typing import Dict, Any

import assemblyai as aai  # type: ignore
from assemblyai import TranscriptError, TranscriptionConfig, SpeechModel

logger = logging.getLogger(__name__)


class TranscriberError(Exception):
    """Custom exception for transcription errors."""

    pass


class AudioTranscriber:
    """Handles audio transcription using AssemblyAI API."""

    # Supported audio file extensions
    SUPPORTED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg", ".webm"}

    def __init__(
        self,
        api_key: str,
        speech_model: str = "best",
        max_retries: int = 3,
        retry_delay: int = 60,
    ) -> None:
        """
        Initialize the AudioTranscriber.

        Args:
            api_key: AssemblyAI API key
            speech_model: Speech model to use ('best' or 'nano')
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
        """
        if not api_key or api_key == "your_api_key_here":
            raise TranscriberError("Valid AssemblyAI API key is required")

        # Set the API key
        aai.settings.api_key = api_key

        # Configure speech model
        model_map = {"best": SpeechModel.best, "nano": SpeechModel.nano}

        if speech_model not in model_map:
            raise TranscriberError(f"Unsupported speech model: {speech_model}")

        self.config = TranscriptionConfig(speech_model=model_map[speech_model])
        self.transcriber = aai.Transcriber(config=self.config)
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        logger.info(f"AudioTranscriber initialized with {speech_model} model")

    def is_supported_file(self, file_path: Path) -> bool:
        """
        Check if the file extension is supported for transcription.

        Args:
            file_path: Path to the audio file

        Returns:
            True if file extension is supported, False otherwise
        """
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS

    def transcribe_file(self, file_path: Path) -> str:
        """
        Transcribe an audio file to text.

        Args:
            file_path: Path to the audio file

        Returns:
            Transcribed text

        Raises:
            TranscriberError: If transcription fails after all retries
        """
        if not file_path.exists():
            raise TranscriberError(f"Audio file does not exist: {file_path}")

        if not self.is_supported_file(file_path):
            raise TranscriberError(
                f"Unsupported file format: {file_path.suffix}. "
                f"Supported formats: {', '.join(sorted(self.SUPPORTED_EXTENSIONS))}"
            )

        logger.info(f"Starting transcription of: {file_path}")

        for attempt in range(self.max_retries):
            try:
                # Convert path to string for AssemblyAI
                transcript = self.transcriber.transcribe(str(file_path))

                if transcript.status == "error":
                    error_msg = f"Transcription failed: {transcript.error}"
                    logger.error(error_msg)
                    raise TranscriberError(error_msg)

                if not transcript.text:
                    logger.warning(f"No text transcribed from {file_path}")
                    return ""

                logger.info(
                    f"Successfully transcribed {file_path} "
                    f"({len(transcript.text)} characters)"
                )
                return str(transcript.text or "")

            except TranscriptError as e:
                logger.error(f"AssemblyAI error on attempt {attempt + 1}: {e}")
                if attempt == self.max_retries - 1:
                    raise TranscriberError(
                        f"Transcription failed after {self.max_retries} attempts: {e}"
                    )

                logger.info(f"Retrying in {self.retry_delay} seconds...")
                time.sleep(self.retry_delay)

            except Exception as e:
                logger.error(f"Unexpected error on attempt {attempt + 1}: {e}")
                if attempt == self.max_retries - 1:
                    raise TranscriberError(
                        f"Transcription failed after {self.max_retries} attempts: {e}"
                    )

                logger.info(f"Retrying in {self.retry_delay} seconds...")
                time.sleep(self.retry_delay)

        # This should never be reached due to the raise statements above
        raise TranscriberError(
            f"Transcription failed after {self.max_retries} attempts"
        )

    def get_transcription_info(self, file_path: Path) -> Dict[str, Any]:
        """
        Get information about a potential transcription without performing it.

        Args:
            file_path: Path to the audio file

        Returns:
            Dictionary with file information
        """
        return {
            "file_path": str(file_path),
            "file_size": file_path.stat().st_size if file_path.exists() else 0,
            "supported": self.is_supported_file(file_path),
            "extension": file_path.suffix.lower(),
        }

    def save_transcript(self, transcript: str, output_path: Path) -> None:
        """
        Save transcript to a text file.

        Args:
            transcript: The transcribed text
            output_path: Path where to save the transcript

        Raises:
            TranscriberError: If saving fails
        """
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(transcript)

            logger.info(f"Transcript saved to: {output_path}")

        except Exception as e:
            raise TranscriberError(f"Failed to save transcript to {output_path}: {e}")

    def transcribe_and_save(
        self, input_path: Path, output_path: Path
    ) -> Dict[str, Any]:
        """
        Transcribe an audio file and save the result.

        Args:
            input_path: Path to the audio file
            output_path: Path where to save the transcript

        Returns:
            Dictionary with transcription results and metadata

        Raises:
            TranscriberError: If transcription or saving fails
        """
        start_time = time.time()

        try:
            # Perform transcription
            transcript = self.transcribe_file(input_path)

            # Save transcript
            self.save_transcript(transcript, output_path)

            end_time = time.time()
            duration = end_time - start_time

            result = {
                "status": "success",
                "input_file": str(input_path),
                "output_file": str(output_path),
                "transcript_length": len(transcript),
                "duration_seconds": round(duration, 2),
                "error": None,
            }

            logger.info(
                f"Transcription completed in {duration:.2f}s: "
                f"{input_path.name} -> {output_path.name}"
            )

            return result

        except Exception as e:
            end_time = time.time()
            duration = end_time - start_time

            result = {
                "status": "error",
                "input_file": str(input_path),
                "output_file": str(output_path),
                "transcript_length": 0,
                "duration_seconds": round(duration, 2),
                "error": str(e),
            }

            logger.error(
                f"Transcription failed after {duration:.2f}s: "
                f"{input_path.name} - {e}"
            )

            raise
