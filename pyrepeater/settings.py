""" settings for pyrepeater"""

from pydantic_settings import BaseSettings


class RepeaterSettings(BaseSettings):
    """settings for repeater hardware"""

    serial_port: str = "/dev/ttyUSB0"
    pre_tx_delay: float = 1.0  # seconds between serial tx enable and playing wav file
    post_tx_delay: float = 1.0  # seconds after tx disable before returning


class ControllerSettings(BaseSettings):
    """settings for controller"""

    fcc_id: str = "WRXC682"
    id_mins: int = 15  # minutes between ID messages
    rpt_info_mins: int = 60  # minutes between repeater info messages
    id_when_idle: bool = False  # send ID messages when idle
    idle_after_mins: int = 10  # minutes of inactivity before idle
