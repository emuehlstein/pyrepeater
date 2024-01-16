""" 
A module to represent a repeater, its status, and provide an interface to it
via a serial port
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
import logging

import serial

logger = logging.getLogger(__name__)


@dataclass
class RepeaterStatus:
    """
    a representation of the "busy" status of the repeater
    ie. is the repeater currently receiving a transmission
    """

    busy: bool = False
    last_rcvd_dt: datetime = datetime.now()


class Repeater:
    """a class to represent a repeater"""

    def __init__(self, serial_port: str, settings, status: RepeaterStatus) -> None:
        self.settings = settings
        self.status = status

        try:
            self.serial = serial.Serial(serial_port, 9600, timeout=1)

            # make sure we're not transmitting
            self.serial.setDTR(False)
            self.serial.setRTS(False)

        except Exception as err:
            logger.error("Unable to open serial port with error: %s", err)
            raise err

        self.settings = settings
    
    def check_status(self) -> RepeaterStatus:
        """
        check the status of the repeater
        """
        if not self.status.busy && self.is_busy():
            self.status.busy = True
            self.status.last_rcvd_dt = datetime.now()
            logger.debug("Repeater busy at %s", self.status.last_rcvd_dt)
        elif self.status.busy && not self.is_busy():
            self.status.busy = False
            logger.debug("Repeater active at %s", datetime.now())

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
            await asyncio.sleep(self.settings.pre_tx_delay)
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
            await asyncio.sleep(self.settings.post_tx_delay)
        except Exception as err:
            logger.error("Unable to set serial port end transmit with error: %s", err)
        return
