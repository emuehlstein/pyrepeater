""" repeater controller and logic"""
import logging
import subprocess
from datetime import datetime, timedelta
from typing import List
from dataclasses import dataclass

from repeater import Repeater

logger = logging.getLogger(__name__)


@dataclass
class ControllerStatus:
    """a class to represent the status of the controller"""

    busy: bool
    last_id: datetime
    last_announcement: datetime
    last_used_dt: datetime
    pending_messages: List[str]


class Controller:
    """a class to represent a controller"""

    def __init__(self, repeater, settings) -> None:
        self.repeater: Repeater = repeater
        self.settings = settings
        self.recorder = None
        self.status = ControllerStatus(
            busy=False,
            last_id=None,
            last_announcement=None,
            last_used_dt=None,
            pending_messages=["sounds/repeater_info.wav", "sounds/cw_id.wav"],
        )

    async def start_controller(self):
        """start the controller"""
        while True:
            # check if repeater is free
            if not self.repeater.is_busy():
                # check if our busy flag is set
                if self.status.busy:
                    # log the change of state then run actions
                    logger.info("Receiver is free.")
                    # mark the repeater as not busy
                    self.status.busy = False

                    await self.when_repeater_is_free()

            # check if repeater is busy
            elif self.repeater.is_busy():
                # check if our busy flag is set
                if not self.status.busy:
                    # log the change of state then run actions
                    logger.info("Receiver is busy.")
                    # mark the repeater as busy
                    self.status.busy = True

                    await self.when_repeater_is_busy()

    async def play_pending_messages(self, wav_files: List[str]) -> None:
        """play the list of wav files in pending_messages"""

        for message in wav_files:
            # play the wav file
            logger.info("Playing wav file: %s", message)
            subprocess.run(
                ["play", "-q", message],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )

        logger.info("Done playing pending messages.  Clearing queue...")
        self.status.pending_messages.clear()

    async def record_to_file(self) -> subprocess.Popen:
        """record incoming transmission to a file, return the recorder"""
        current_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        recording_name = f"recordings/{current_time}.wav"

        # start recording
        logger.info("Recording to file: %s", recording_name)
        recorder = subprocess.Popen(
            ["rec", "-q", "-c", "1", "-r", "8000", recording_name]
        )
        return recorder

    async def when_repeater_is_free(self) -> None:
        """actions to take when the repeater is free"""
        # stop recording
        if self.recorder:
            self.recorder.terminate()
            logger.info("Stopped recording.")

        # mark the last used time
        self.status.last_used_dt = datetime.now()

        if self.status.pending_messages:
            await self.repeater.serial_enable_tx(self.repeater)
            await self.play_pending_messages(self.status.pending_messages)
            await self.repeater.serial_disable_tx(self.repeater)
            self.status.last_announcement = datetime.now()

    async def when_repeater_is_busy(self) -> None:
        """actions to take when the repeater is busy"""
        # start recording
        self.recorder = await self.record_to_file()

    async def check_for_timed_events(self) -> None:
        """check for timed events ex. CW ID"""
        # repeater info + ID announcements
        if (
            timedelta.total_seconds(datetime.now() - self.status.last_announcement)
            >= self.settings.rpt_info_mins * 60
        ):
            logger.info(
                "Last announcement was over %s mins ago.  Playing announcement.",
                self.settings.rpt_info_mins,
            )
            self.status.pending_messages.append("sounds/repeater_info.wav")
            self.status.pending_messages.append("sounds/cw_id.wav")
            self.status.last_announcement = datetime.now()

        # cw only announcements
        if (
            timedelta.total_seconds(datetime.now() - last_announcement)
            >= self.settings.id_mins * 60
        ):
            logger.info(
                "Last CW ID was over %s minutes ago.  Playing ID.",
                self.settings.id_mins,
            )
            self.status.pending_messages.append("sounds/cw_id.wav")
            last_announcement = datetime.now()
