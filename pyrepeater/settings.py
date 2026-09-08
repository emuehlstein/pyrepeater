""" settings for pyrepeater"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# .env lives next to this module so settings load regardless of CWD
ENV_FILE = Path(__file__).resolve().parent / ".env"


class RepeaterSettings(BaseSettings):
    """settings for repeater hardware"""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore"
    )

    serial_port: str = "/dev/ttyUSB0"
    pre_tx_delay: float = 1.0  # seconds between serial tx enable and playing wav file
    post_tx_delay: float = 1.0  # seconds after tx disable before returning


class ControllerSettings(BaseSettings):
    """settings for controller"""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore"
    )

    fcc_id: str = "WRXC682"
    id_mins: int = 15  # minutes between ID messages
    rpt_info_mins: int = 60  # minutes between repeater info messages
    id_when_asleep: bool = False  # send ID messages when asleep
    rpt_info_when_asleep: bool = False  # send repeater info messages when asleep
    sleep_after_mins: int = 10  # minutes of inactivity before sleep
    wake_after_sec: int = 2  # seconds of activity before leaving sleep
    min_rec_secs: int = 2  # minimum seconds to record
    parrot_mode: bool = False  # play back recordings after each transmission

    dtmf_commands_enabled: bool = True  # decode DTMF from recordings for remote control
    cmd_parrot_toggle: str = "999"  # DTMF digits to toggle parrot mode
    cmd_force_id: str = "312"  # DTMF digits to force an immediate CW ID
    cmd_sleep_toggle: str = "73"  # DTMF digits to force sleep/wake toggle
    cmd_status: str = "311"  # DTMF digits to play the status/announcement message
