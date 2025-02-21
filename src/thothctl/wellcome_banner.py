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
    ascii_banner = pyfiglet.figlet_format("\t\t\t thothctl \t", font="graffiti")
    print(Fore.LIGHTMAGENTA_EX + ascii_banner + Fore.RESET)
    print(
        Fore.LIGHTMAGENTA_EX
        + "___ 🕵  The CLI for your Internal Developer Control plane. 🕵  ____"
        + Fore.RESET
    )
