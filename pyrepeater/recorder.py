""" manages recording """

import logging
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta

from repeater import Repeater

logger = logging.getLogger(__name__)


@dataclass
class Recording:
    """a class to represent a recorder"""

    proc: subprocess.Popen
    start_time: datetime
    file_name: str


class RecordingManager:
    """a class to manage recodrings"""

    def __init__(self, repeater: Repeater, settings) -> None:
        self.recording: Recording = None
        self.repeater = repeater
        self.settings = settings

    async def update_status(self) -> None:
        """if repeater is busy, start recording, if it becomes free, stop recording"""
        if await self.repeater.is_busy() and not self.recording:
            await self.start_recording()
        elif not await self.repeater.is_busy() and self.recording:
            await self.stop_recording()

    async def is_recording(self) -> bool:
        """is the recorder recording?"""
        return self.recording is not None

    async def start_recording(self) -> None:
        """start a recording"""
        current_time = datetime.now()
        current_str = current_time.strftime("%Y-%m-%d_%H-%M-%S")
        recording_name = f"recordings/{current_str}.wav"

        # start recording
        logger.debug("Recording to file: %s", recording_name)
        process = subprocess.Popen(  # pylint: disable=consider-using-with
            ["rec", "-q", "-c", "1", "-r", "8000", recording_name]
        )
        self.recording = Recording(
            proc=process, start_time=current_time, file_name=recording_name
        )

    async def stop_recording(self) -> None:
        """stop the recording"""
        if not self.recording:
            return

        # check how long the recording was
        recording_time = timedelta.total_seconds(
            datetime.now() - self.recording.start_time
        )

        # end recording
        self.recording.proc.terminate()

        logger.debug("Stopped recording. (%s s)", recording_time)

        # if recording was less than min_rec_secs, delete it
        if recording_time < self.settings.min_rec_secs:
            logger.debug(
                "Recording was less than %s seconds.  Deleting recording.",
                self.settings.min_rec_secs,
            )
            subprocess.run(["rm", "-f", self.recording.file_name], check=False)

        else:
            logger.info(
                "Recorded %s secs to %s", recording_time, self.recording.file_name
            )

        self.recording = None
