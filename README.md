# thothctl
Package for accelerating the adoption of Internal Frameworks, enable reusing and interaction with the Internal Developer Platform. 

# Use cases
- Accelerate the adoption of DevSecOps IaC Framework created by DevSecOps Sophos Team.

- Accelerate the reuse of common projects, PoCs, and pattern for data analytics, machine learning, Cloud, and DevSecOps projects.

# Express Sheet

```bash
$ thothctl -h

usage: thothctl [-h] [-d DIRECTORY_CODE] [-v] [-bv] [-os {Linux/Debian}] [-sw] [-l] {init,scan,doc,transform,validate,hand-wk,automate,inventory} ...

Accelerate DevSecOps IaC projects implementation and developer tasks.

options:
  -h, --help            show this help message and exit
  -d DIRECTORY_CODE, --directory_code DIRECTORY_CODE
                        Root path for code project (default: .)
  -v, --version         Get Version
  -bv, --bootstrap_env  Install base tools for you environment.
  -os {Linux/Debian}, --operation_system {Linux/Debian}
                        Install base tools for you environment, (default: Linux/Debian). Use with --bootstrap_env Allowed values: 'Linux/Debian'
  -sw, --sync_terraform_workspaces
                        Synchronize terraform workspaces for dependencies tree base on terragrunt + terraform framework
  -l, --verbose         Enable debug Mode

Commands:
  Command and functionalities

  {init,scan,doc,transform,validate,hand-wk,automate,inventory}
                        thothctl Commands
    init                Initialize project, provide project name,example: thothctl init -pj <project-name>
    scan                Scan code using tools example: thothctl scan -t checkov
    doc                 Create and document IaC using terraform-docsexample: thothctl doc -d . -dm local_module
    transform           Transform your code to use terramate and terragrunt together or singleexample: thothctl -d . -l transform -j -y $main_branch
    validate            Check project structure based on default framework or custom framework. For example: thothctl validate -cp -d -cm hard
    hand-wk             Handling workspaces operations for example, check if already exists the backend configuration, synchronize for modules and resources according to IaC Framework, example: thothctl hand-wk -sw
    automate            Automate tasks for example adding resources folders based on your configurations, Create code component template based on project structure define into .thothcf.tomlexample: thothctl add -cn test -ct     
                        resource -cph ./resources/myresource
    inventory           Transform your code to use terramate and terragrunt together or singleexample: thothctl inventory -ci -if all -check

Thanks for using thothctl!


```

# Requirements
 - Linux Environment or Windows environment

> This documentation uses wsl with ubuntu 20.04 but you can use other superior version

## OS Packages

- dot or graphviz

You can install them with:

### Windows
 Chocolatey packages Graphviz for **Windows**.

`choco install graphviz`
### Linux
Install packages with apt for Linux/Debian
- 
```bash 
sudo apt install graphviz -y
```
- python >= 3.8 
    - check: `python --version` 

- wkhtmltopdf

You can install it using: 

```commandline
apt-get install wkhtmltopdf
```

> Visit [wkhtmltopdf](https://github.com/JazzCore/python-pdfkit/wiki/Installing-wkhtmltopdf) for more.

### AddOns

If you are going to send messages to Microsoft Teams channel you must set an environment variable with name `webhook`
> Visit [Webhooks and connectors](https://docs.microsoft.com/en-us/microsoftteams/platform/webhooks-and-connectors/what-are-webhooks-and-connectors) for more.

### Python packages

There are many dependencies for thothctl functions, these dependencies are automatically installed when run `pip install` command.


# Install

```Bash
pip install --upgrade thothctl
```

## Extras
### Enable autocomplete
Argcomplete provides easy, extensible command line tab completion of arguments for your Python application.

It makes two assumptions:

* You’re using bash or zsh as your shell

* You’re using argparse to manage your command line arguments/options

Argcomplete is particularly useful if your program has lots of options or subparsers, and if your program can dynamically suggest completions for your argument/option values (for example, if the user is browsing resources over the network).
Run: 
```bash
activate-global-python-argcomplete
```
and to make sure that bash knows about this script, you use
```bash

echo 'eval "$(register-python-argcomplete thothctl)"' >> ~/.bashrc
source ~/.bashrc

```