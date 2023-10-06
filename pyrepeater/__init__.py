""" a simple repeater controller with periodic id """

import asyncio
import logging
import os
import re
import subprocess
from datetime import datetime

from repeater import Repeater
from settings import RepeaterSettings

logger = logging.getLogger("pyrepeater")
logging.basicConfig(level=logging.DEBUG)

# temp list of wav files to play
pending_messages = ["sounds/repeater_info.wav", "sounds/cw_id.wav"]


async def play_pending_messages(pending_messages):
    """play the list of wav files in pending_messages"""

    for message in pending_messages:
        # play the wav file
        logger.info("Playing wav file: %s", message)
        os.system(f"play {message}")

    logger.info("Done playing pending messages.  Clearing queue...")
    pending_messages.clear()


async def main():
    """ main execution """
    r_s = RepeaterSettings()
    rep = Repeater(r_s.serial_port)

    # it's busy until we know otherwise
    _busy = True

    # we don't have a recorder until the first rcv event
    recorder = None

    try:
        # loop checking if the repeater is busy, send pending messages if not
        while True:
            if not rep.is_busy():
                if _busy:
                    # log the change of state then set _busy to False
                    logger.info("Receiver is free.")
                    if recorder:
                        recorder.terminate()
                        logger.info("Stopped recording.")
                    _busy = False

                if pending_messages:
                    await rep.serial_enable_tx(rep)
                    await play_pending_messages(pending_messages)
                    await rep.serial_disable_tx(rep)
            else:
                if not _busy:
                    # log the change of state then set _busy to True
                    logger.info("Receiver is busy.")
                    current_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                    recording_name = f"recordings/{current_time}.wav"

                    # start recording
                    logger.info("Recording to file: %s", recording_name)
                    recorder = subprocess.Popen(
                        ["rec", "-q", "-c", "1", "-r", "8000", recording_name]
                    )
                    _busy = True

    except KeyboardInterrupt:
        logger.info("Exiting")
        rep.close()


if __name__ == "__main__":
    asyncio.run(main())
