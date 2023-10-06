from pydantic_settings import BaseSettings


class RepeaterSettings(BaseSettings):
    fcc_id: str = "WRXC682"
    serial_port: str = "/dev/tty.usbserial-FTDCZX23"
    pre_tx_delay: float = 1 # seconds between serial tx enable and playing wav file
