""" manages recording """

import asyncio
import asyncio.subprocess
import logging
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from .repeater import Repeater

logger = logging.getLogger(__name__)

RECORDINGS_DIR = Path(__file__).resolve().parent / "recordings"


@dataclass
class Recording:
    """a class to represent a recorder"""

    proc: subprocess.Popen
    start_time: datetime
    file_name: str


class RecordingManager:
    """a class to manage recodrings"""

    def __init__(self, repeater: Repeater, settings) -> None:
        self.recording: Recording | None = None
        self.repeater = repeater
        self.settings = settings

    async def update_status(self) -> str | None:
        """
        if repeater is busy, start recording, if it becomes free, stop recording

        returns the file name of a just-completed recording (kept, not deleted
        for being too short), or None if no recording just finished
        """
        if await self.repeater.is_busy() and not self.recording:
            await self.start_recording()
        elif not await self.repeater.is_busy() and self.recording:
            return await self.stop_recording()
        return None

    async def is_recording(self) -> bool:
        """is the recorder recording?"""
        return self.recording is not None

    async def start_recording(self) -> None:
        """start a recording"""
        current_time = datetime.now()
        current_str = current_time.strftime("%Y-%m-%d_%H-%M-%S")
        RECORDINGS_DIR.mkdir(exist_ok=True)
        recording_name = str(RECORDINGS_DIR / f"{current_str}.wav")

        # start recording
        logger.debug("Recording to file: %s", recording_name)
        process = subprocess.Popen(  # pylint: disable=consider-using-with
            ["rec", "-q", "-c", "1", "-r", "48000", recording_name]
        )
        self.recording = Recording(
            proc=process, start_time=current_time, file_name=recording_name
        )

    async def stop_recording(self) -> str | None:
        """stop the recording, returning the file name if it was kept"""
        if not self.recording:
            return None

        # check how long the recording was
        recording_time = timedelta.total_seconds(
            datetime.now() - self.recording.start_time
        )

        # end recording; wait so sox flushes and closes the wav file
        self.recording.proc.terminate()
        try:
            await asyncio.to_thread(self.recording.proc.wait, 5)
        except subprocess.TimeoutExpired:
            logger.warning("Recorder did not exit after terminate; killing it.")
            self.recording.proc.kill()
            await asyncio.to_thread(self.recording.proc.wait)

        logger.debug("Stopped recording. (%s s)", recording_time)

        file_name = self.recording.file_name

        # if recording was less than min_rec_secs, delete it
        if recording_time < self.settings.min_rec_secs:
            logger.debug(
                "Recording was less than %s seconds.  Deleting recording.",
                self.settings.min_rec_secs,
            )
            try:
                os.remove(file_name)
            except OSError as err:
                logger.warning("Unable to delete %s: %s", file_name, err)
            file_name = None

        else:
            logger.info("Recorded %s secs to %s", recording_time, file_name)
            # normalize recording to -1dBFS so parrot playback is consistent
            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".wav")
            os.close(tmp_fd)
            proc = await asyncio.create_subprocess_exec(
                "sox", file_name, tmp_path, "norm", "-1"
            )
            returncode = await proc.wait()
            if returncode == 0:
                shutil.move(tmp_path, file_name)
            else:
                logger.warning("Normalization failed for %s; keeping original.", file_name)
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

        self.recording = None
        return file_name
