#!/usr/bin/env python3
"""
Script to enable autocomplete for thothctl using Click's built-in completion support.
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def main():
    """Set up shell completion for thothctl using Click's completion mechanism."""
    shell = os.environ.get("SHELL", "").split("/")[-1] or "bash"
    
    if shell not in ["bash", "zsh", "fish"]:
        print(f"Warning: Shell '{shell}' may not be fully supported. Defaulting to bash completion.")
        shell = "bash"
    
    # Generate the completion script content
    if shell == "bash":
        completion_cmd = 'eval "$(_THOTHCTL_COMPLETE=bash_source thothctl)"'
    elif shell == "zsh":
        completion_cmd = 'eval "$(_THOTHCTL_COMPLETE=zsh_source thothctl)"'
    elif shell == "fish":
        completion_cmd = 'eval "$(_THOTHCTL_COMPLETE=fish_source thothctl)"'
    
    # Determine the appropriate config file
    if shell == "bash":
        config_file = os.path.expanduser("~/.bashrc")
    elif shell == "zsh":
        config_file = os.path.expanduser("~/.zshrc")
    elif shell == "fish":
        config_file = os.path.expanduser("~/.config/fish/config.fish")
        os.makedirs(os.path.dirname(config_file), exist_ok=True)
    
    # Print instructions
    print(f"\nTo enable autocompletion for thothctl in {shell}, add the following line to {config_file}:")
    print(f"\n    {completion_cmd}\n")
    print(f"For example, you can add it with:")
    print(f"\n    echo '{completion_cmd}' >> {config_file}\n")
    print("Then restart your shell or run:")
    print(f"\n    source {config_file}\n")
    
    # Offer to add it automatically
    answer = input(f"Would you like to add this line to {config_file} automatically? (y/n): ")
    if answer.lower() in ('y', 'yes'):
        try:
            # Check if the line already exists
            if Path(config_file).exists():
                with open(config_file, 'r') as f:
                    content = f.read()
                if completion_cmd in content:
                    print(f"\nCompletion is already configured in {config_file}")
                    return 0
            
            # Add the completion command
            with open(config_file, 'a') as f:
                f.write(f"\n# ThothCTL autocomplete\n{completion_cmd}\n")
            
            print(f"\nAutocomplete configuration added to {config_file}")
            print(f"Please restart your shell or run 'source {config_file}' to activate it.")
            
            # Offer to source the file immediately
            answer = input("Would you like to activate completion now? (y/n): ")
            if answer.lower() in ('y', 'yes'):
                subprocess.run(["source", config_file], shell=True)
                print("Completion activated!")
        except Exception as e:
            print(f"Error adding to {config_file}: {e}")
            sys.exit(1)
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
