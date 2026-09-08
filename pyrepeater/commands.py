""" decodes and dispatches DTMF remote commands found in completed recordings """

import logging
import re
import subprocess

logger = logging.getLogger(__name__)

DTMF_LINE_RE = re.compile(r"^DTMF:\s*([0-9A-D*#])", re.MULTILINE)


def decode_dtmf(wav_file: str) -> str:
    """run multimon-ng against a wav file and return the decoded digit string

    Applies a 600-1800 Hz bandpass filter before decoding. Without this, wideband
    noise from the radio (squelch tail, carrier) swamps the DTMF tones and
    multimon-ng fails to lock on despite the tones being present in the audio.
    """
    # pipe: sox bandpass filter → multimon-ng stdin
    sox_proc = subprocess.Popen(
        ["sox", wav_file, "-t", "wav", "-", "sinc", "600-1800"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    result = subprocess.run(
        ["multimon-ng", "-a", "DTMF", "-t", "wav", "-"],
        stdin=sox_proc.stdout,
        capture_output=True,
        text=True,
        check=False,
    )
    sox_proc.wait()
    digits = "".join(DTMF_LINE_RE.findall(result.stdout))
    return digits


class CommandProcessor:
    """decodes DTMF from a recording and maps it to a known command name"""

    def __init__(self, settings) -> None:
        self.settings = settings
        self.commands = {
            settings.cmd_parrot_toggle: "parrot_toggle",
            settings.cmd_force_id: "force_id",
            settings.cmd_sleep_toggle: "sleep_toggle",
            settings.cmd_status: "status",
        }

    async def process_recording(self, wav_file: str) -> str | None:
        """decode a recording for DTMF and return the matched command name, if any"""
        if not self.settings.dtmf_commands_enabled:
            return None

        digits = decode_dtmf(wav_file)
        if not digits:
            return None

        # log every decoded sequence for audit purposes (no PIN gate is enforced)
        logger.info("Decoded DTMF digits %s from %s", digits, wav_file)

        command = self.commands.get(digits)
        if command:
            logger.info("Recognized command '%s' from digits %s", command, digits)
        return command
