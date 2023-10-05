import logging
from time import sleep
import serial

logger = logging.getLogger(__name__)


class Repeater:
    def __init__(self, serial_port: str, settings: dict = None) -> None:
        try:
            self.serial = serial.Serial(serial_port, 9600, timeout=1)
            
            # make sure we're not transmitting
            self.serial.setDTR(False)
            self.serial.setRTS(False)
            
        except Exception as err:
            logger.error("Unable to open serial port with error: %s", err)
            raise err

        self.settings = settings

    def is_busy(self) -> bool:
        """
        check if the repeater is busy
        """
        return self.serial.dsr

    async def serial_enable_tx(self, repeater) -> None:
        """
        enable the serial port for transmit
        """
        try:
            ser = repeater.serial
            ser.setDTR(True)
            ser.setRTS(True)
            # sleep .5 for the relay to kick in
            asyncio.sleep(.5)
        except Exception as err:
            logger.error("Unable to set serial port for transmit with error: %s", err)
        return

    async def serial_disable_tx(self, repeater) -> None:
        """
        disable the serial port for transmit
        """
        try:
            ser = repeater.serial
            ser.setDTR(False)
            ser.setRTS(False)
        except Exception as err:
            logger.error("Unable to set serial port end transmit with error: %s", err)
        return
