""" settings for pyrepeater"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class RepeaterSettings(BaseSettings):
    """settings for repeater hardware"""

    serial_port: str = "/dev/ttyUSB0"
    pre_tx_delay: float = 1.0  # seconds between serial tx enable and playing wav file
    post_tx_delay: float = 1.0  # seconds after tx disable before returning

    class Settings(BaseSettings):
        """settings for settings"""

        model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


class ControllerSettings(BaseSettings):
    """settings for controller"""

    fcc_id: str = "WRXC682"
    id_mins: int = 15  # minutes between ID messages
    rpt_info_mins: int = 60  # minutes between repeater info messages
    id_when_asleep: bool = False  # send ID messages when asleep
    rpt_info_when_asleep: bool = False  # send repeater info messages when asleep
    sleep_after_mins: int = 10  # minutes of inactivity before sleep
    wake_after_sec: int = 2  # seconds of activity before leaving sleep
    min_rec_secs: int = 2  # minimum seconds to record

    class Settings(BaseSettings):
        """settings for settings"""

        model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
