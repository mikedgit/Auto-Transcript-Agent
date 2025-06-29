"""Folder monitoring system for Auto-Transcript-Agent."""

import logging
import time
import uuid
from pathlib import Path
from typing import List, Set, Callable, Optional, Dict
from threading import Thread, Event, Lock
from dataclasses import dataclass

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from .transcriber import AudioTranscriber

logger = logging.getLogger(__name__)


@dataclass
class ProcessedFile:
    """Information about a processed file."""

    path: Path
    processed_at: float
    status: str  # 'success', 'error', 'skipped'
    error_message: Optional[str] = None
    processing_id: Optional[str] = None


class AudioFileHandler(FileSystemEventHandler):
    """Handles file system events for audio files."""

    def __init__(self, transcriber: AudioTranscriber, callback: Callable[[Path], None]):
        """
        Initialize the audio file handler.

        Args:
            transcriber: AudioTranscriber instance to check file compatibility
            callback: Function to call when a new audio file is detected
        """
        super().__init__()
        self.transcriber = transcriber
        self.callback = callback
        self.processing_files: Set[str] = set()

    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation events."""
        if not event.is_directory:
            self._handle_file_event(Path(str(event.src_path)))

    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification events."""
        if not event.is_directory:
            self._handle_file_event(Path(str(event.src_path)))

    def _handle_file_event(self, file_path: Path) -> None:
        """
        Handle a file system event for a potential audio file.

        Args:
            file_path: Path to the file that was created or modified
        """
        # Skip if already processing this file
        file_key = str(file_path)
        if file_key in self.processing_files:
            return

        # Skip if not a supported audio file
        if not self.transcriber.is_supported_file(file_path):
            logger.debug(f"Skipping unsupported file: {file_path}")
            return

        # Skip temporary files or files that might still be copying
        if file_path.name.startswith(".") or file_path.name.startswith("~"):
            logger.debug(f"Skipping temporary file: {file_path}")
            return

        logger.info(f"New audio file detected: {file_path}")

        # Mark as processing to avoid duplicates
        self.processing_files.add(file_key)

        try:
            # Call the callback to process the file
            self.callback(file_path)
        finally:
            # Remove from processing set
            self.processing_files.discard(file_key)


class FolderMonitor:
    """Monitors a folder for new audio files and processes them."""

    def __init__(
        self,
        input_dir: Path,
        output_dir: Path,
        done_dir: Path,
        transcriber: AudioTranscriber,
        poll_interval: int = 5,
    ):
        """
        Initialize the folder monitor.

        Args:
            input_dir: Directory to monitor for new audio files
            output_dir: Directory to save transcripts
            done_dir: Directory to move processed files
            transcriber: AudioTranscriber instance
            poll_interval: Polling interval in seconds for fallback monitoring
        """
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.done_dir = done_dir
        self.transcriber = transcriber
        self.poll_interval = poll_interval

        # Ensure directories exist
        self.input_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.done_dir.mkdir(parents=True, exist_ok=True)

        # Set up watchdog observer
        self.observer = Observer()
        self.event_handler = AudioFileHandler(transcriber, self._process_file)

        # Threading controls
        self._stop_event = Event()
        self._poll_thread: Optional[Thread] = None

        # Track processed files
        self.processed_files: List[ProcessedFile] = []
        
        # File processing protection
        self._processing_lock = Lock()
        self._currently_processing: Dict[str, str] = {}  # file_path -> processing_id

        logger.info("FolderMonitor initialized:")
        logger.info(f"  Input directory: {self.input_dir}")
        logger.info(f"  Output directory: {self.output_dir}")
        logger.info(f"  Done directory: {self.done_dir}")

    def start(self) -> None:
        """Start monitoring the input directory."""
        logger.info("Starting folder monitoring...")

        # Start watchdog observer
        self.observer.schedule(self.event_handler, str(self.input_dir), recursive=False)
        self.observer.start()
        logger.info("File system watcher started")

        # Start polling thread as fallback
        self._poll_thread = Thread(target=self._poll_directory, daemon=True)
        self._poll_thread.start()
        logger.info(f"Polling thread started (interval: {self.poll_interval}s)")

        # Process any existing files
        self._process_existing_files()

    def stop(self) -> None:
        """Stop monitoring the input directory."""
        logger.info("Stopping folder monitoring...")

        # Stop the observer
        if self.observer.is_alive():
            self.observer.stop()
            self.observer.join()
            logger.info("File system watcher stopped")

        # Stop polling thread
        self._stop_event.set()
        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=5)
            logger.info("Polling thread stopped")

    def _process_existing_files(self) -> None:
        """Process any audio files that already exist in the input directory."""
        logger.info("Checking for existing audio files...")

        existing_files = []
        for file_path in self.input_dir.iterdir():
            if file_path.is_file() and self.transcriber.is_supported_file(file_path):
                existing_files.append(file_path)

        if existing_files:
            logger.info(f"Found {len(existing_files)} existing audio files to process")
            for file_path in existing_files:
                self._process_file(file_path)
        else:
            logger.info("No existing audio files found")

    def _poll_directory(self) -> None:
        """Polling fallback in case file system events are missed."""
        logger.debug("Polling thread started")

        while not self._stop_event.is_set():
            try:
                # Check for new files
                for file_path in self.input_dir.iterdir():
                    if (
                        file_path.is_file()
                        and self.transcriber.is_supported_file(file_path)
                        and not self._is_recently_processed(file_path)
                    ):

                        logger.debug(f"Polling detected file: {file_path}")
                        self._process_file(file_path)

            except Exception as e:
                logger.error(f"Error during directory polling: {e}")

            # Wait for next poll
            self._stop_event.wait(self.poll_interval)

    def _is_recently_processed(self, file_path: Path) -> bool:
        """
        Check if a file was recently processed to avoid reprocessing.

        Args:
            file_path: Path to check

        Returns:
            True if file was recently processed, False otherwise
        """
        # Consider a file recently processed if it was processed in the last hour
        recent_threshold = time.time() - 3600

        for processed_file in self.processed_files:
            if (
                processed_file.path == file_path
                and processed_file.processed_at > recent_threshold
            ):
                return True

        return False

    def _process_file(self, file_path: Path) -> None:
        """
        Process a single audio file with race condition protection.

        Args:
            file_path: Path to the audio file to process
        """
        file_key = str(file_path)
        processing_id = str(uuid.uuid4())[:8]  # Short unique ID
        
        # Check if already being processed (race condition protection)
        with self._processing_lock:
            if file_key in self._currently_processing:
                existing_id = self._currently_processing[file_key]
                logger.info(f"File already being processed by {existing_id}, skipping: {file_path.name}")
                return
            
            # Mark as being processed
            self._currently_processing[file_key] = processing_id

        logger.info(f"[{processing_id}] Processing file: {file_path}")

        try:
            # Check if file still exists (might have been moved/deleted)
            if not file_path.exists():
                logger.warning(f"[{processing_id}] File no longer exists: {file_path}")
                return

            # Wait a moment to ensure file is fully written
            self._wait_for_file_stability(file_path)

            # Generate output path
            output_path = self.output_dir / f"{file_path.stem}.txt"

            # Check if transcript already exists
            if output_path.exists():
                logger.info(f"[{processing_id}] Transcript already exists, skipping: {output_path}")
                self._move_to_done(file_path)
                self._record_processed_file(
                    file_path, "skipped", "Transcript already exists", processing_id
                )
                return

            # Perform transcription
            self.transcriber.transcribe_and_save(file_path, output_path)

            # Move original file to done directory
            self._move_to_done(file_path)

            # Record successful processing
            self._record_processed_file(file_path, "success", None, processing_id)

            logger.info(f"[{processing_id}] Successfully processed: {file_path.name}")

        except Exception as e:
            logger.error(f"[{processing_id}] Failed to process {file_path}: {e}")
            self._record_processed_file(file_path, "error", str(e), processing_id)
        finally:
            # Always clean up processing state
            with self._processing_lock:
                self._currently_processing.pop(file_key, None)

    def _wait_for_file_stability(self, file_path: Path, max_wait: int = 30) -> None:
        """
        Wait for a file to become stable (not being written to).

        Args:
            file_path: Path to the file
            max_wait: Maximum time to wait in seconds
        """
        start_time = time.time()
        last_size = 0
        stable_count = 0

        while time.time() - start_time < max_wait:
            try:
                current_size = file_path.stat().st_size
                if current_size == last_size:
                    stable_count += 1
                    if stable_count >= 3:  # Stable for 3 checks
                        break
                else:
                    stable_count = 0

                last_size = current_size
                time.sleep(1)

            except FileNotFoundError:
                logger.warning(
                    f"File disappeared while waiting for stability: {file_path}"
                )
                break
            except Exception as e:
                logger.warning(f"Error checking file stability: {e}")
                break

    def _move_to_done(self, file_path: Path) -> None:
        """
        Move a processed file to the done directory with improved error handling.

        Args:
            file_path: Path to the file to move
        """
        try:
            # Check if source file still exists
            if not file_path.exists():
                logger.warning(f"Source file no longer exists, may have been moved already: {file_path.name}")
                return

            done_path = self.done_dir / file_path.name

            # Handle filename conflicts
            counter = 1
            while done_path.exists():
                stem = file_path.stem
                suffix = file_path.suffix
                done_path = self.done_dir / f"{stem}_{counter}{suffix}"
                counter += 1

            # Perform the move
            file_path.rename(done_path)
            logger.info(
                f"Moved to done directory: {file_path.name} -> {done_path.name}"
            )

        except FileNotFoundError:
            logger.warning(f"File was already moved or deleted: {file_path.name}")
        except Exception as e:
            logger.error(f"Failed to move file to done directory: {e}")

    def _record_processed_file(
        self, file_path: Path, status: str, error_message: Optional[str] = None, processing_id: Optional[str] = None
    ) -> None:
        """
        Record information about a processed file.

        Args:
            file_path: Path to the processed file
            status: Processing status ('success', 'error', 'skipped')
            error_message: Optional error message
            processing_id: Optional unique processing identifier
        """
        processed_file = ProcessedFile(
            path=file_path,
            processed_at=time.time(),
            status=status,
            error_message=error_message,
            processing_id=processing_id,
        )

        self.processed_files.append(processed_file)

        # Keep only the last 1000 processed files to avoid memory issues
        if len(self.processed_files) > 1000:
            self.processed_files = self.processed_files[-1000:]

    def get_statistics(self) -> dict:
        """
        Get processing statistics.

        Returns:
            Dictionary with processing statistics
        """
        total_files = len(self.processed_files)
        successful = sum(1 for f in self.processed_files if f.status == "success")
        errors = sum(1 for f in self.processed_files if f.status == "error")
        skipped = sum(1 for f in self.processed_files if f.status == "skipped")

        return {
            "total_processed": total_files,
            "successful": successful,
            "errors": errors,
            "skipped": skipped,
            "success_rate": successful / total_files if total_files > 0 else 0,
            "is_monitoring": self.observer.is_alive() if self.observer else False,
        }

    def get_recent_files(self, hours: int = 24) -> List[ProcessedFile]:
        """
        Get files processed in the last N hours.

        Args:
            hours: Number of hours to look back

        Returns:
            List of recently processed files
        """
        cutoff_time = time.time() - (hours * 3600)
        return [f for f in self.processed_files if f.processed_at > cutoff_time]
