"""Get Versions."""
import pyfiglet
from colorama import Fore


def get_version(version):
    """
    Get version of the bot.

    :param version:
    :return:
    """
    print(Fore.MAGENTA + "v" + version + Fore.MAGENTA)
    return version


def simple_banner():
    """
    Get simple banner.

    :return:
    """
    ascii_banner = pyfiglet.figlet_format("\t\t\t thothctl \t", font="bubble")
    print(Fore.LIGHTMAGENTA_EX + ascii_banner + Fore.RESET)
    print(
        Fore.MAGENTA
        + "___ 🕵 Accelerate your deployments with Thothctl - Your CLI  Infrastructure Platform Interface. 🕵  ____"
        + Fore.RESET
    )
