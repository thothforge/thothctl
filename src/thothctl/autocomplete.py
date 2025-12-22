#!/usr/bin/env python3
"""
Script to enable autocomplete for thothctl using Click's built-in completion support.
"""

import os
import sys
import subprocess
import shutil
import platform
from pathlib import Path

def main():
    """Set up shell completion for thothctl using Click's completion mechanism."""
    system = platform.system()
    
    if system == "Windows":
        # Windows PowerShell completion
        shell = "powershell"
        completion_cmd = 'Register-ArgumentCompleter -Native -CommandName thothctl -ScriptBlock { param($wordToComplete, $commandAst, $cursorPosition); $env:_THOTHCTL_COMPLETE="powershell_complete"; $env:COMP_WORDS=$commandAst.ToString(); $env:COMP_CWORD=$cursorPosition; thothctl 2>$null }'
        config_file = Path.home() / "Documents" / "PowerShell" / "Microsoft.PowerShell_profile.ps1"
        config_file.parent.mkdir(parents=True, exist_ok=True)
    else:
        # Unix shells
        shell = os.environ.get("SHELL", "").split("/")[-1] or "bash"
        
        if shell not in ["bash", "zsh", "fish"]:
            print(f"Warning: Shell '{shell}' may not be fully supported. Defaulting to bash completion.")
            shell = "bash"
        
        # Generate the completion script content
        if shell == "bash":
            completion_cmd = 'eval "$(_THOTHCTL_COMPLETE=bash_source thothctl)"'
            config_file = Path.home() / ".bashrc"
        elif shell == "zsh":
            completion_cmd = 'eval "$(_THOTHCTL_COMPLETE=zsh_source thothctl)"'
            config_file = Path.home() / ".zshrc"
        elif shell == "fish":
            completion_cmd = 'eval "$(_THOTHCTL_COMPLETE=fish_source thothctl)"'
            config_file = Path.home() / ".config" / "fish" / "config.fish"
            config_file.parent.mkdir(parents=True, exist_ok=True)
    
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
