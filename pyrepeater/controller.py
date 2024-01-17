""" repeater controller manages the state of the repeater, recordings, and announcements"""
import logging
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List

from repeater import Repeater, RepeaterStatus

logger = logging.getLogger(__name__)


@dataclass
class SleepStatus:
    """a class to represent sleep status of the repeater ie. it has gone unused for some time"""

    sleep: bool = False  # is sleep?
    start_dt: datetime = datetime.now()  # when did sleep start?
    end_dt: datetime = None  # when did sleep end?
    sleep_wait_start: datetime = None  # when did we start waiting for sleep?
    wake_wait_start: datetime = None  # when did we start waiting for wake?


@dataclass
class ControllerStatus:
    """a class to represent the status of the controller and repeater announcments"""

    last_id: datetime
    last_announcement: datetime
    pending_messages: List[str]


@dataclass
class Recording:
    """a class to represent a recorder"""

    proc: subprocess.Popen
    start_time: datetime
    file_name: str


class RecordingManager:
    """a class to manage recodrings"""

    async def __init__(self, repeater: Repeater, settings) -> None:
        self.recording: Recording = None
        self.repeater = repeater
        self.settings = settings

    async def update_status(self) -> None:
        """if repeater is busy, start recording, if it becomes free, stop recording"""
        if self.repeater.is_busy() and not self.recording:
            await self.start_recording()
        elif not self.repeater.is_busy() and self.recording:
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
        process = subprocess.Popen(
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

        self.recording = None


class SleepManager:
    """a class which knows about repeater status and mangages sleep status"""

    def __init__(self, repeater, settings) -> None:
        self.repeater: Repeater = repeater
        self.settings = settings
        self.sleep_status: SleepStatus = SleepStatus()

    async def sleep_timer(self) -> None:
        """sleep timer"""

        # sleep after 'sleep_after_mins' minutes of inactivity
        if not self.sleep_status.sleep and (
            timedelta.total_seconds(datetime.now() - self.repeater.last_rcvd_dt)
            >= self.settings.sleep_after_mins * 60
        ):
            logger.info(
                "Entering sleep state.  Last used over %s mins ago.",
                self.settings.sleep_after_mins,
            )
            self.sleep_status.sleep = True
            self.sleep_status.start_dt = datetime.now()

        # wake after 'wake_after_sec' seconds of activity
        if self.sleep_status.sleep and (
            timedelta.total_seconds(datetime.now() - self.repeater.last_rcvd_dt)
            <= self.settings.wake_after_sec
        ):
            logger.info(
                "Leaving sleep state.  Active for %s seconds.",
                self.settings.wake_after_sec,
            )
            self.sleep_status.sleep = False
            self.sleep_status.end_dt = datetime.now()

    async def is_sleeping(self):
        """is the repeater sleeping?"""
        return self.sleep_status.sleep


class Controller:
    """a class to represent a controller"""

    def __init__(self, repeater, settings) -> None:
        self.repeater: Repeater = repeater
        self.settings = settings
        self.recording_mgr: RecordingManager = None
        self.sleep_mgr: SleepManager = None
        self.sleep_status: SleepStatus = (SleepStatus(),)
        self.repeater_status: RepeaterStatus = (RepeaterStatus(),)
        self.status: ControllerStatus = ControllerStatus(
            last_id=datetime.now(),
            last_announcement=datetime.now(),
            pending_messages=[],
        )

    async def start_controller(self):
        """start the controller"""

        # assign some private status vars
        _wait_before_active = False

        # create managers
        self.sleep_mgr = SleepManager(self.repeater, self.settings, self.status)
        self.recording_mgr = RecordingManager(self.repeater, self.settings, self.status)

        while True:
            # check for timed events
            await self.repeater.check_status()
            await self.recording_mgr.update_status()
            await self.check_for_timed_events()

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

    async def when_repeater_is_free(self) -> None:
        """actions to take when the repeater is free"""

        if self.status.pending_messages:
            await self.repeater.serial_enable_tx(self.repeater)
            await self.play_pending_messages(self.status.pending_messages)
            await self.repeater.serial_disable_tx(self.repeater)

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

        if not self.sleep_mgr.is_sleeping() or self.settings.id_when_sleep:
            logger.info(
                "Last CW ID was over %s minutes ago.  Playing ID.",
                self.settings.id_mins,
            )
            self.status.pending_messages.append("sounds/cw_id.wav")
            self.status.last_id = datetime.now()

    async def check_for_timed_events(self) -> None:
        """check for timed events ex. CW ID"""
        await self.sleep_mgr.sleep_timer()
        await self.repeaterinfo_timer()
        await self.cwid_timer()
