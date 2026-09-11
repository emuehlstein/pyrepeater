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

    # stdlib HTTP control API (announce/status); bind to LAN/tailnet only
    http_enabled: bool = True  # serve the local HTTP control API
    http_host: str = "0.0.0.0"  # interface to bind the control API to
    http_port: int = 8080  # port for the control API

    dtmf_commands_enabled: bool = True  # decode DTMF from recordings for remote control
    cmd_parrot_toggle: str = "999"  # DTMF digits to toggle parrot mode
    cmd_force_id: str = "312"  # DTMF digits to force an immediate CW ID
    cmd_sleep_toggle: str = "73"  # DTMF digits to force sleep/wake toggle
    cmd_status: str = "311"  # DTMF digits to play the status/announcement message
    cmd_net_toggle: str = "556"  # DTMF digits to toggle net mode

    # day/night/net modes
    day_start: str = "07:00"  # HH:MM, local time, start of day mode
    day_end: str = "22:00"  # HH:MM, local time, start of night mode
    day_sleep_after_mins: int = 240  # minutes of inactivity before sleep, during the day

    # daytime time+weather announcement (on the :30 of each hour)
    time_wx_enabled: bool = True  # announce time/weather + CW ID at :30 during the day
    wx_lat: float = 0.0  # latitude for NWS weather lookup
    wx_lon: float = 0.0  # longitude for NWS weather lookup
