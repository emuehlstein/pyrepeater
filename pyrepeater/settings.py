from pydantic_settings import BaseSettings


class RepeaterSettings(BaseSettings):
    fcc_id: str = "WRXC682"
    serial_port: str = "/dev/tty.usbserial-FTDCZX23"
