"""ThothCTL ASCII art banner."""

THOTHCTL_BANNER = """
  _____ _           _   _      ____ _____ _     
 |_   _| |__   ___ | |_| |__  / ___|_   _| |    
   | | | '_ \ / _ \| __| '_ \| |     | | | |    
   | | | | | | (_) | |_| | | | |___  | | | |___ 
   |_| |_| |_|\___/ \__|_| |_|\____| |_| |_____|
   
   📜 Internal Developer Platform CLI
"""

THOTHCTL_BANNER_COLORED = """
\033[94m  _____ _           _   _      ____ _____ _     \033[0m
\033[94m |_   _| |__   ___ | |_| |__  / ___|_   _| |    \033[0m
\033[96m   | | | '_ \ / _ \| __| '_ \| |     | | | |    \033[0m
\033[96m   | | | | | | (_) | |_| | | | |___  | | | |___ \033[0m
\033[95m   |_| |_| |_|\___/ \__|_| |_|\____| |_| |_____|\033[0m
   
   📜 \033[1mInternal Developer Platform CLI\033[0m
"""

def get_banner(colored: bool = True) -> str:
    """Get ThothCTL banner.
    
    Args:
        colored: Return colored version if True
        
    Returns:
        ASCII art banner string
    """
    return THOTHCTL_BANNER_COLORED if colored else THOTHCTL_BANNER
