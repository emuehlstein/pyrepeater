import asyncio
import logging
import os

from repeater import Repeater
from settings import RepeaterSettings


logger = logging.getLogger("pyrepeater")
logging.basicConfig(level=logging.DEBUG)


pending_messages = ["sounds/current_weather.wav", "sounds/cw_id.wav"]


async def play_pending_messages(pending_messages):
    """play the list of wav files in pending_messages"""

    for message in pending_messages:
        # play the wav file
        logger.info("Playing wav file: %s", message)
        os.system(f"afplay {message}")

    logger.info("Done playing pending messages.  Clearing queue...")
    pending_messages.clear()


async def main():
    rs = RepeaterSettings()
    rep = Repeater(rs.serial_port)

    # it's busy until we know otherwise
    _busy = True

    try:
        # loop checking if the repeater is busy, send pending messages if not
        while True:
            if not rep.is_busy():
                if _busy:
                    logger.info("Receiver is free.")
                    _busy = False

                if pending_messages:
                    await rep.serial_enable_tx(rep)
                    await play_pending_messages(pending_messages)
                    await rep.serial_disable_tx(rep)
            else:
                if not _busy:
                    logger.info("Receiver is busy.")
                    _busy = True

    except KeyboardInterrupt:
        logger.info("Exiting")
        rep.close()


if __name__ == "__main__":
    asyncio.run(main())
