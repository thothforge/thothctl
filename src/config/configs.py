"""Set Configurations for project setup."""
from colorama import Fore


def set_conventions():
    """
    Set conventions for terraform projects.

    :return:
    """
    conventions = ["modules", "files"]
    # Modules convention
    print(f"{Fore.LIGHTBLUE_EX}[1] Modules convention: \n")
    print(
        """modules_convention/
├── main.tf
├── resources
│   ├── compute
│   │   ├── main.tf
│   │   ├── outputs.tf
│   │   └── variables.tf
│   ├── iam
│   │   ├── main.tf
│   │   ├── outputs.tf
│   │   └── variables.tf
│   └── storage
│       ├── main.tf
│       ├── outputs.tf
│       └── variables.tf
├── outputs.tf
└── variables.tf
"""
    )
    # Files convention
    print("[2] Files Convention: \n")
    print(
        """files_convention/
└── resources
    ├── data-store
    │   └── storage.tf
    ├── some-stack-name
    │   ├── iam.tf
    │   ├── main.tf
    │   └── pubsub.tf
    └── web-server
        ├── iam.tf
        └── main.tf
"""
    )
    try:
        x = int(input("Choose terraform convention project (Input a number): "))
        if x == 0 or x == 1:
            print(f"{Fore.GREEN}✅   {conventions[x]} was selected.")
            return conventions[x]
        else:
            print(f"{Fore.RED}❌   No convention for {x} input {Fore.RESET}")

    except ValueError:
        print(f"{Fore.RED}❌ Invalid input. Please enter a valid integer. {Fore.RESET}")


set_conventions()
