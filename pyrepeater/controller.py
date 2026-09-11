""" repeater controller manages the state of the repeater, recordings, and announcements"""
import logging
import asyncio
import asyncio.subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from .repeater import Repeater
from .recorder import RecordingManager
from .commands import CommandProcessor
from .httpapi import ControlApi
from .modes import Mode, current_mode
from .announcer import fetch_weather, build_announcement_text, generate_wav

logger = logging.getLogger(__name__)

SOUNDS_DIR = Path(__file__).resolve().parent / "sounds"


def sound(name: str) -> str:
    """absolute path to a bundled sound file"""
    return str(SOUNDS_DIR / name)


@dataclass
class SleepStatus:
    """a class to represent sleep status of the repeater ie. it has gone unused for some time"""

    sleep: bool = False  # is sleep?
    start_dt: datetime = field(default_factory=datetime.now)  # when did sleep start?
    end_dt: Optional[datetime] = None  # when did sleep end?
    sleep_wait_start: Optional[datetime] = None  # when did we start waiting for sleep?
    wake_wait_start: Optional[datetime] = None  # when did we start waiting for wake?


@dataclass
class ControllerStatus:
    """a class to represent the status of the controller and repeater announcments"""

    last_id: datetime
    last_announcement: datetime
    pending_messages: List[str]
    parrot_mode: bool = False  # runtime-toggleable, seeded from settings at startup
    net_mode: bool = False  # runtime-toggleable; overrides day/night mode when set
    last_time_wx: datetime = field(default_factory=lambda: datetime(1970, 1, 1))


class SleepManager:
    """a class which knows about repeater status and mangages sleep status"""

    def __init__(self, repeater, settings) -> None:
        self.repeater: Repeater = repeater
        self.settings = settings
        self.sleep_status: SleepStatus = SleepStatus()

    async def sleep_timer(self, mode: Mode) -> None:
        """sleep timer, called periodically by the main loop"""

        if mode == Mode.NET:
            # nets are never interrupted by sleep
            if self.sleep_status.sleep:
                logger.info("Leaving sleep state: net mode is active.")
                self.sleep_status.sleep = False
                self.sleep_status.end_dt = datetime.now()
            return

        sleep_after_mins = (
            self.settings.day_sleep_after_mins
            if mode == Mode.DAY
            else self.settings.sleep_after_mins
        )

        # sleep after 'sleep_after_mins' minutes of inactivity
        if not self.sleep_status.sleep and (
            timedelta.total_seconds(
                datetime.now() - await self.repeater.check_last_rcvd()
            )
            >= sleep_after_mins * 60
        ):
            logger.info(
                "Entering sleep state.  Last used over %s mins ago.",
                sleep_after_mins,
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

    async def is_sleeping(self) -> bool:
        """is the repeater sleeping?"""
        return self.sleep_status.sleep

    async def force_toggle(self) -> None:
        """force a sleep/wake toggle, bypassing the inactivity timers"""
        self.sleep_status.sleep = not self.sleep_status.sleep
        if self.sleep_status.sleep:
            self.sleep_status.start_dt = datetime.now()
        else:
            self.sleep_status.end_dt = datetime.now()


class Controller:
    """a class to represent a controller"""

    def __init__(self, repeater, settings) -> None:
        self.repeater: Repeater = repeater
        self.settings = settings
        self.recording_mgr: RecordingManager = None
        self.sleep_mgr: SleepManager = None
        self.command_processor: CommandProcessor = None
        self.control_api: ControlApi = None
        self._time_wx_in_flight = False  # guards against overlapping background fetch/TTS tasks
        self.status: ControllerStatus = ControllerStatus(
            last_id=datetime(1970, 1, 1),
            last_announcement=datetime(1970, 1, 1),
            pending_messages=[],
            parrot_mode=settings.parrot_mode,
        )

    @staticmethod
    def sound(name: str) -> str:
        """absolute path to a bundled sound file (also used by the control API)"""
        return sound(name)

    async def start_controller(self):
        """start the controller"""

        # create managers
        self.sleep_mgr = SleepManager(self.repeater, self.settings)
        self.recording_mgr = RecordingManager(self.repeater, self.settings)
        self.command_processor = CommandProcessor(self.settings)

        # optional stdlib HTTP control API; never fatal to the repeater
        if self.settings.http_enabled:
            self.control_api = ControlApi(self, self.settings)
            await self.control_api.start()

        # main controller loop; failsafe guarantees PTT is dropped on any exit
        try:
            while True:
                # check the repeater status
                await self.repeater.check_status()

                # update the recording status
                finished_recording = await self.recording_mgr.update_status()

                if finished_recording:
                    command = await self.command_processor.process_recording(
                        finished_recording
                    )
                    if command:
                        # command transmissions are control-only, not parroted back
                        await self.execute_command(command)
                    elif self.status.parrot_mode:
                        # in parrot mode, play back the just-finished recording (range testing)
                        logger.info(
                            "Parrot mode: queueing playback of %s", finished_recording
                        )
                        self.status.pending_messages.append(finished_recording)

                # check for timed events (ex. annoucements and CW ID)
                await self.check_for_timed_events()

                # otherwise, if repeater is not busy, play pending messages
                if not await self.repeater.is_busy() and self.status.pending_messages:
                    await self.play_pending_messages(self.status.pending_messages)

                await asyncio.sleep(0.05)
        finally:
            if self.control_api:
                await self.control_api.stop()
            await self.repeater.serial_disable_tx()

    async def play_pending_messages(self, wav_files: List[str]) -> None:
        """play the list of wav files in pending_messages"""
        if not self.status.pending_messages:
            logger.debug("No pending messages to play.")
            return

        logger.debug("Playing pending messages...")

        # start tx; ensure PTT is always released even if playback fails
        await self.repeater.serial_enable_tx()

        try:
            for message in wav_files:
                # play the wav file
                logger.info("Playing wav file: %s", message)
                proc = await asyncio.create_subprocess_exec(
                    "play",
                    "-q",
                    message,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await proc.wait()
        finally:
            # stop tx
            await self.repeater.serial_disable_tx()

        logger.debug("Done playing pending messages.  Clearing queue...")
        self.status.pending_messages.clear()

    async def repeaterinfo_timer(self) -> None:
        """
        checks if the repeater info announcement should be played based on the
        last time it was played and the 'rpt_info_mins' setting
        """
        if (
            timedelta.total_seconds(datetime.now() - self.status.last_announcement)
            <= self.settings.rpt_info_mins * 60
        ):
            return

        if not await self.sleep_mgr.is_sleeping() or self.settings.rpt_info_when_asleep:
            logger.info(
                "Last announcement was over %s mins ago.  Playing announcement.",
                self.settings.rpt_info_mins,
            )
            self.status.pending_messages.append(sound("repeater_info.wav"))
            self.status.last_announcement = datetime.now()
            self.status.pending_messages.append(sound("cw_id.wav"))
            self.status.last_id = datetime.now()

    async def cwid_timer(self) -> None:
        """
        checks if the CW ID should be played based on the last time it was
        played and the 'id_mins' setting
        """

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
            self.status.pending_messages.append(sound("cw_id.wav"))
            self.status.last_id = datetime.now()

    async def time_wx_timer(self, mode: Mode) -> None:
        """
        on the :30 of each daytime hour, announce the time and weather
        followed by a CW ID; skipped entirely while asleep
        """
        if mode != Mode.DAY or not self.settings.time_wx_enabled:
            return

        now = datetime.now()
        if now.minute != 30:
            return

        already_fired_this_hour = (
            self.status.last_time_wx.date() == now.date()
            and self.status.last_time_wx.hour == now.hour
        )
        if already_fired_this_hour or self._time_wx_in_flight:
            return

        if await self.sleep_mgr.is_sleeping():
            return

        # mark immediately so the ~50ms poll loop doesn't refire while the
        # background task below is still fetching weather / generating audio
        self.status.last_time_wx = now
        self._time_wx_in_flight = True
        asyncio.create_task(self._play_time_wx_announcement())

    async def _play_time_wx_announcement(self) -> None:
        """fetch weather, render the announcement wav, and queue it plus a CW ID"""
        try:
            weather = await fetch_weather(self.settings.wx_lat, self.settings.wx_lon)
            text = build_announcement_text(weather)
            wav_path = SOUNDS_DIR / "_time_wx.wav"
            if await generate_wav(text, wav_path):
                logger.info("Queueing time/weather announcement: %s", text)
                self.status.pending_messages.append(str(wav_path))
                self.status.pending_messages.append(sound("cw_id.wav"))
                self.status.last_id = datetime.now()
            else:
                logger.warning("Time/weather announcement skipped; wav generation failed")
        finally:
            self._time_wx_in_flight = False

    async def check_for_timed_events(self) -> None:
        """check for timed events ex. CW ID"""
        mode = current_mode(self.settings, self.status.net_mode)
        await self.sleep_mgr.sleep_timer(mode)
        if mode != Mode.NET:
            await self.repeaterinfo_timer()
        await self.cwid_timer()
        await self.time_wx_timer(mode)

    async def execute_command(self, command: str) -> None:
        """execute a remote DTMF command"""
        # audible confirmation that the command was received, played before the
        # command's own result announcement (if any)
        self.status.pending_messages.append(sound("command_ack.wav"))

        if command == "parrot_toggle":
            self.status.parrot_mode = not self.status.parrot_mode
            logger.info("DTMF command: parrot mode now %s", self.status.parrot_mode)
            announcement = (
                "parrot_mode_on.wav"
                if self.status.parrot_mode
                else "parrot_mode_off.wav"
            )
            self.status.pending_messages.append(sound(announcement))
        elif command == "force_id":
            logger.info("DTMF command: forcing CW ID")
            self.status.pending_messages.append(sound("cw_id.wav"))
            self.status.last_id = datetime.now()
        elif command == "sleep_toggle":
            await self.sleep_mgr.force_toggle()
            logger.info(
                "DTMF command: sleep toggled to %s", self.sleep_mgr.sleep_status.sleep
            )
        elif command == "status":
            logger.info("DTMF command: playing status announcement")
            self.status.pending_messages.append(sound("repeater_info.wav"))
            self.status.last_announcement = datetime.now()
        elif command == "net_toggle":
            self.status.net_mode = not self.status.net_mode
            logger.info("DTMF command: net mode now %s", self.status.net_mode)
        else:
            logger.warning("Unknown DTMF command: %s", command)
