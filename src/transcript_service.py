"""Main service for Auto-Transcript-Agent."""

import logging
import signal
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any

import click

from .config import (
    load_config,
    setup_logging,
    ConfigError,
    validate_directories,
    Config,
)
from .transcriber import AudioTranscriber
from .monitor import FolderMonitor

logger = logging.getLogger(__name__)


class TranscriptService:
    """Main service class for the Auto-Transcript-Agent."""

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize the transcript service.

        Args:
            config_path: Optional path to configuration file
        """
        self.config: Config
        self.transcriber: Optional[AudioTranscriber] = None
        self.monitor: Optional[FolderMonitor] = None
        self.running = False
        self._last_stats_time: float = 0.0

        # Load configuration
        try:
            self.config = load_config(config_path)
            setup_logging(self.config)
            logger.info("Auto-Transcript-Agent service initialized")

        except ConfigError as e:
            print(f"Configuration error: {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Initialization error: {e}", file=sys.stderr)
            sys.exit(1)

    def start(self) -> None:
        """Start the transcript service."""
        if self.running:
            logger.warning("Service is already running")
            return

        try:
            logger.info("Starting Auto-Transcript-Agent service...")

            # Validate directories
            validate_directories(self.config)

            # Initialize transcriber
            self.transcriber = AudioTranscriber(
                api_key=self.config.assemblyai_api_key,
                speech_model=self.config.speech_model,
                max_retries=self.config.max_retries,
                retry_delay=self.config.retry_delay,
            )

            # Initialize folder monitor
            self.monitor = FolderMonitor(
                input_dir=self.config.input_dir,
                output_dir=self.config.output_dir,
                done_dir=self.config.done_dir,
                transcriber=self.transcriber,
                poll_interval=self.config.poll_interval,
            )

            # Start monitoring
            self.monitor.start()
            self.running = True

            logger.info("Auto-Transcript-Agent service started successfully")
            logger.info(f"Monitoring: {self.config.input_dir}")
            logger.info(f"Output to: {self.config.output_dir}")
            logger.info(f"Done files: {self.config.done_dir}")

        except Exception as e:
            logger.error(f"Failed to start service: {e}")
            self.stop()
            raise

    def stop(self) -> None:
        """Stop the transcript service."""
        if not self.running:
            return

        logger.info("Stopping Auto-Transcript-Agent service...")

        try:
            if self.monitor:
                self.monitor.stop()

            self.running = False
            logger.info("Auto-Transcript-Agent service stopped")

        except Exception as e:
            logger.error(f"Error during service shutdown: {e}")

    def run(self) -> None:
        """Run the service until interrupted."""
        # Set up signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        try:
            self.start()

            # Main service loop
            while self.running:
                try:
                    time.sleep(1)

                    # Periodically log statistics
                    if hasattr(self, "_last_stats_time"):
                        if time.time() - self._last_stats_time > 3600:  # Every hour
                            self._log_statistics()
                    else:
                        self._last_stats_time = time.time()

                except KeyboardInterrupt:
                    logger.info("Received keyboard interrupt")
                    break

        except Exception as e:
            logger.error(f"Service error: {e}")
        finally:
            self.stop()

    def _signal_handler(self, signum: int, frame: Optional[object]) -> None:
        """Handle system signals for graceful shutdown."""
        if signum == signal.SIGINT:
            signal_name = "SIGINT"
        elif signum == signal.SIGTERM:
            signal_name = "SIGTERM"
        else:
            signal_name = f"Signal {signum}"
        logger.info(f"Received {signal_name}, shutting down...")
        self.running = False

    def _log_statistics(self) -> None:
        """Log service statistics."""
        if self.monitor:
            stats = self.monitor.get_statistics()
            logger.info(f"Service statistics: {stats}")
            self._last_stats_time = time.time()

    def get_status(self) -> Dict[str, Any]:
        """
        Get current service status.

        Returns:
            Dictionary with service status information
        """
        status: Dict[str, Any] = {
            "running": self.running,
            "config_loaded": self.config is not None,
            "transcriber_initialized": self.transcriber is not None,
            "monitor_active": (
                self.monitor is not None and self.monitor.observer.is_alive()
                if self.monitor
                else False
            ),
        }

        if self.config:
            status["directories"] = {
                "input": str(self.config.input_dir),
                "output": str(self.config.output_dir),
                "done": str(self.config.done_dir),
            }

        if self.monitor:
            status["statistics"] = self.monitor.get_statistics()
            status["recent_files"] = [
                {
                    "path": str(f.path),
                    "status": f.status,
                    "processed_at": f.processed_at,
                    "error": f.error_message,
                }
                for f in self.monitor.get_recent_files(hours=1)
            ]

        return status


# CLI Commands


@click.group()
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Path to configuration file",
)
@click.pass_context
def cli(ctx: click.Context, config: Optional[Path]) -> None:
    """Auto-Transcript-Agent: Audio transcription service."""
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config


@cli.command()
@click.pass_context
def run(ctx: click.Context) -> None:
    """Run the transcript service."""
    config_path = ctx.obj.get("config_path")

    try:
        service = TranscriptService(config_path)
        service.run()
    except KeyboardInterrupt:
        click.echo("Service interrupted by user")
    except Exception as e:
        click.echo(f"Service error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show service status."""
    config_path = ctx.obj.get("config_path")

    try:
        service = TranscriptService(config_path)
        status_info = service.get_status()

        click.echo("Auto-Transcript-Agent Status:")
        click.echo(f"  Running: {status_info['running']}")
        click.echo(f"  Config loaded: {status_info['config_loaded']}")
        click.echo(
            f"  Transcriber initialized: {status_info['transcriber_initialized']}"
        )
        click.echo(f"  Monitor active: {status_info['monitor_active']}")

        if "directories" in status_info:
            click.echo("\nDirectories:")
            for key, value in status_info["directories"].items():
                click.echo(f"  {key.capitalize()}: {value}")

        if "statistics" in status_info:
            stats = status_info["statistics"]
            click.echo("\nStatistics:")
            click.echo(f"  Total processed: {stats['total_processed']}")
            click.echo(f"  Successful: {stats['successful']}")
            click.echo(f"  Errors: {stats['errors']}")
            click.echo(f"  Skipped: {stats['skipped']}")
            click.echo(f"  Success rate: {stats['success_rate']:.1%}")

    except Exception as e:
        click.echo(f"Status check failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("audio_file", type=click.Path(exists=True, path_type=Path))
@click.argument("output_file", type=click.Path(path_type=Path), required=False)
@click.pass_context
def transcribe(
    ctx: click.Context, audio_file: Path, output_file: Optional[Path]
) -> None:
    """Transcribe a single audio file."""
    config_path = ctx.obj.get("config_path")

    try:
        service = TranscriptService(config_path)

        if not service.transcriber:
            # Initialize transcriber if service isn't running
            service.transcriber = AudioTranscriber(
                api_key=service.config.assemblyai_api_key,
                speech_model=service.config.speech_model,
                max_retries=service.config.max_retries,
                retry_delay=service.config.retry_delay,
            )

        # Determine output file
        if not output_file:
            output_file = audio_file.with_suffix(".txt")

        click.echo(f"Transcribing {audio_file} to {output_file}...")

        result = service.transcriber.transcribe_and_save(audio_file, output_file)

        if result["status"] == "success":
            click.echo("✓ Transcription completed successfully")
            click.echo(f"  Duration: {result['duration_seconds']}s")
            click.echo(f"  Transcript length: {result['transcript_length']} characters")
            click.echo(f"  Output: {result['output_file']}")
        else:
            click.echo(f"✗ Transcription failed: {result['error']}", err=True)
            sys.exit(1)

    except Exception as e:
        click.echo(f"Transcription failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--force", "-f", is_flag=True, help="Overwrite existing configuration")
def init_config(force: bool) -> None:
    """Initialize configuration file."""
    from .config import create_sample_config, get_default_config_path

    config_path = get_default_config_path()

    if config_path.exists() and not force:
        click.echo(f"Configuration file already exists: {config_path}")
        click.echo("Use --force to overwrite")
        return

    try:
        create_sample_config(config_path)
        click.echo(f"Configuration file created: {config_path}")
        click.echo("Please edit the file with your actual settings")
    except Exception as e:
        click.echo(f"Failed to create configuration: {e}", err=True)
        sys.exit(1)


def main() -> None:
    """Main entry point for the service."""
    cli()


if __name__ == "__main__":
    main()
