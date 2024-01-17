""" repeater controller manages the state of the repeater, recordings, and announcements"""
import logging
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List

from repeater import Repeater, RepeaterStatus
from recorder import RecordingManager

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
            timedelta.total_seconds(
                datetime.now() - await self.repeater.check_last_rcvd()
            )
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
            timedelta.total_seconds(
                datetime.now() - await self.repeater.check_last_rcvd()
            )
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
            last_id=datetime(1970, 1, 1),
            last_announcement=datetime(1970, 1, 1),
            pending_messages=[],
        )

    async def start_controller(self):
        """start the controller"""

        # assign some private status vars
        _wait_before_active = False

        # create managers
        self.sleep_mgr = SleepManager(self.repeater, self.settings)
        self.recording_mgr = RecordingManager(self.repeater, self.settings)

        while True:
            # check for timed events
            await self.repeater.check_status()
            await self.recording_mgr.update_status()
            await self.check_for_timed_events()

            if not await self.repeater.is_busy():
                await self.when_repeater_is_free()

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
            >= self.settings.rpt_info_mins * 60
        ):
            return

        if not await self.sleep_mgr.is_sleeping() or self.settings.rpt_info_when_asleep:
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

        if not await self.sleep_mgr.is_sleeping() or self.settings.id_when_asleep:
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
