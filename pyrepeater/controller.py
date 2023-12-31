""" repeater controller and logic"""
import logging
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List

from repeater import Repeater

logger = logging.getLogger(__name__)


@dataclass
class ControllerStatus:
    """a class to represent the status of the controller"""

    busy: bool  # is the repeater receiving a transmission
    idle: bool  # has the repeater been idle for idle_after_mins
    last_id: datetime
    last_announcement: datetime
    last_used_dt: datetime
    idle_wait_start: datetime
    idle_start_dt: datetime
    pending_messages: List[str]


@dataclass
class Recorder:
    """a class to represent a recorder"""

    proc: subprocess.Popen
    start_time: datetime
    file_name: str


class Controller:
    """a class to represent a controller"""

    def __init__(self, repeater, settings) -> None:
        self.repeater: Repeater = repeater
        self.settings = settings
        self.recorder: Recorder = None
        self.status = ControllerStatus(
            busy=False,
            idle=False,
            last_id=datetime.now(),
            last_announcement=datetime.now(),
            last_used_dt=datetime.now(),
            idle_start_dt=None,
            idle_wait_start=None,
            pending_messages=["sounds/repeater_info.wav", "sounds/cw_id.wav"],
        )

    async def start_controller(self):
        """start the controller"""

        # assign some private status vars
        _wait_before_active = False

        while True:
            # check for timed events
            await self.check_for_timed_events()

            # check if repeater is free
            if not self.repeater.is_busy():
                # check if our busy flag is set
                if self.status.busy:
                    # log the change of state then run actions
                    logger.debug("Receiver is free.")
                    # mark the repeater as not busy
                    self.status.busy = False

                if _wait_before_active:
                    # end the idle wait
                    logger.debug("Returning to idle...")
                    _wait_before_active = False

                else:
                    if self.recorder:
                        _rec_length = timedelta.total_seconds(
                            datetime.now() - self.recorder.start_time
                        )
                        logger.info("Recorded %.1f seconds.", _rec_length)

                await self.when_repeater_is_free()

            # check if repeater is busy
            elif self.repeater.is_busy():
                # check if our busy flag is set
                if not self.status.busy:
                    # log the change of state then run actions
                    logger.debug("Receiver is busy.")
                    # mark the repeater as busy
                    self.status.busy = True

                # check if our idle flag is set, start waiting for idle
                if self.status.idle and not _wait_before_active:
                    logger.debug("Delaying switch to idle...")
                    self.status.idle_wait_start = datetime.now()
                    _wait_before_active = True

                # check if we've been idle long enough, set to idle
                if _wait_before_active and (
                    timedelta.total_seconds(
                        datetime.now() - self.status.idle_wait_start
                    )
                    >= self.settings.active_after_sec
                ):
                    _inactivity_mins = (
                        timedelta.total_seconds(
                            datetime.now() - self.status.idle_start_dt
                        )
                        / 60
                    )

                    # log the change of state then run actions
                    logger.info(
                        "Ending idle state after %s mins of inactivity.",
                        _inactivity_mins,
                    )

                    # mark the repeater as active
                    self.status.idle = False

                    # reset the idle start time, reset flag
                    self.status.idle_wait_start = None
                    _wait_before_active = False

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

    async def record_to_file(self) -> Recorder:
        """record incoming transmission to a file, return the recorder"""
        current_time = datetime.now()
        current_str = current_time.strftime("%Y-%m-%d_%H-%M-%S")
        recording_name = f"recordings/{current_str}.wav"

        # start recording
        logger.debug("Recording to file: %s", recording_name)
        process = subprocess.Popen(
            ["rec", "-q", "-c", "1", "-r", "8000", recording_name]
        )
        rec = Recorder(proc=process, start_time=current_time, file_name=recording_name)
        return rec

    async def stop_recording(self) -> None:
        """stop recording"""
        if not self.recorder:
            return

        # check how long the recording was
        recording_time = timedelta.total_seconds(
            datetime.now() - self.recorder.start_time
        )

        # end recording
        self.recorder.proc.terminate()

        logger.debug("Stopped recording. (%s s)", recording_time)

        # if recording was less than min_rec_secs, delete it
        if recording_time < self.settings.min_rec_secs:
            logger.debug(
                "Recording was less than %s seconds.  Deleting recording.",
                self.settings.min_rec_secs,
            )
            subprocess.run(["rm", "-f", self.recorder.file_name], check=False)

        self.recorder = None

    async def when_repeater_is_free(self) -> None:
        """actions to take when the repeater is free"""
        # stop recording
        await self.stop_recording()

        if self.status.pending_messages:
            await self.repeater.serial_enable_tx(self.repeater)
            await self.play_pending_messages(self.status.pending_messages)
            await self.repeater.serial_disable_tx(self.repeater)

    async def when_repeater_is_busy(self) -> None:
        """actions to take when the repeater is busy"""
        # start recording
        if not self.recorder:
            self.recorder = await self.record_to_file()

        # mark the last used time
        self.status.last_used_dt = datetime.now()

    async def idle_timer(self) -> None:
        """idle timer"""
        if not self.status.idle and (
            timedelta.total_seconds(datetime.now() - self.status.last_used_dt)
            >= self.settings.idle_after_mins * 60
        ):
            logger.info(
                "Entering idle state.  Last used over %s mins ago.",
                self.settings.idle_after_mins,
            )
            self.status.idle = True
            self.status.idle_start_dt = datetime.now()

    async def repeaterinfo_timer(self) -> None:
        """repeater info timer"""
        if (
            timedelta.total_seconds(datetime.now() - self.status.last_announcement)
            <= self.settings.rpt_info_mins * 60
        ):
            return

        logger.info(
            "Last announcement was over %s mins ago.  Playing announcement.",
            self.settings.rpt_info_mins,
        )
        self.status.pending_messages.append("sounds/repeater_info.wav")
        self.status.last_announcement = datetime.now()
        self.status.pending_messages.append("sounds/cw_id.wav")
        self.status.last_id = datetime.now()

    async def cwid_timer(self) -> None:
        """when to play CW ID"""

        if (
            timedelta.total_seconds(datetime.now() - self.status.last_id)
            <= self.settings.id_mins * 60
        ):
            return

        if not self.status.idle or self.settings.id_when_idle:
            logger.info(
                "Last CW ID was over %s minutes ago.  Playing ID.",
                self.settings.id_mins,
            )
            self.status.pending_messages.append("sounds/cw_id.wav")
            self.status.last_id = datetime.now()

    async def check_for_timed_events(self) -> None:
        """check for timed events ex. CW ID"""
        await self.idle_timer()
        await self.repeaterinfo_timer()
        await self.cwid_timer()
