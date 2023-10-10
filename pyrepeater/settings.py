""" settings for pyrepeater"""

from pydantic_settings import BaseSettings


class RepeaterSettings(BaseSettings):
    """settings for repeater hardware"""

    serial_port: str = "/dev/ttyUSB0"
    pre_tx_delay: float = 1.0  # seconds between serial tx enable and playing wav file


class ControllerSettings(BaseSettings):
    """settings for controller"""

    fcc_id: str = "WRXC682"
    id_mins: int = 15  # minutes between ID messages
    rpt_info_mins: int = 60  # minutes between repeater info messages
