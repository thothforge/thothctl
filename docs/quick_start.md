# Quick Start

## Help Command

For getting the use cases you can run `thothctl -h`
```commandline
$ thothctl --help
Usage: thothctl [OPTIONS] COMMAND [ARGS]...

  ThothForge CLI - The Open Source Internal Developer Platform CLI

Options:
  --version                  Show the version and exit.
  --debug                    Enable debug mode
  -d, --code-directory PATH  Configuration file path
  --help                     Show this message and exit.

Commands:
  check      Initialize and setup project configurations
  document   Initialize and setup project configurations
  generate   Generate IaC from rules, use cases, and components
  init       Initialize and setup project configurations
  inventory  Create Inventory for the iac composition.
  list       List Projects and Spaces managed by thothctl locally
  mcp        Model Context Protocol (MCP) server for ThothCTL
  project    Convert, clean up and manage the current project
  remove     Remove Projects manage by thothctl
  scan       Scan infrastructure code for security issues.
```
## Initialize a space

Run init command to get the options
```commandline
thothctl init space --help
Usage: thothctl init space [OPTIONS]

  Initialize a new space

Options:
  -ot, --orchestration-tool [terragrunt|terramate|none]
                                  Default orchestration tool for the space
  -ta, --terraform-auth [none|token|env_var]
                                  Terraform registry authentication method
  -tr, --terraform-registry TEXT  Terraform registry URL
  -vcs, --vcs-provider [azure_repos|github|gitlab]
                                  Version Control System provider
  -d, --description TEXT          Description of the space
  -s, --space-name TEXT           Name of the space  [required]
  --help                          Show this message and exit.
```
Run for example:

```bash
$ thothctl init space -vcs github -d "Default local github testing" -s lab-github
ℹ️ 🌌 Creating new space: lab-github
ℹ️ 🚀 Initializing space: lab-github
✅ 🔧 Space 'lab-github' configuration created
ℹ️ 🔗 Created github VCS configuration
ℹ️ 🏗️ Created Terraform registry configuration
ℹ️ 🔄 Created Terragrunt orchestration configuration
ℹ️ 📁 Space 'lab-github' directory structure created at /home/labvel/.thothcf/spaces/lab-github
✅ 🎉 Space 'lab-github' initialized successfully!
✅ ✨ Space 'lab-github' is ready to use!
ℹ️ 💡 You can now create projects in this space with:
ℹ️    thothctl init project --project-name <name> --space lab-github
```
## Initialize a new project

Initialize project based on templates, custom framework or void template.


> Just support Azure DevOps Integration - We're working for more integrations 
### Init command summary options

![Init Command summary](img/commnad_init.png)


### Use cases

#### Create project from void template

You can create a project without content, just a void template with base structure. For example:

```commandline
$  thothctl init -pj <project_name>

```
![](img/init_project.gif)

#### Create a new project based on existing templates
> You must have a Personal Access Token for list the projects in Azure DevOps and clone in your local machine.

In this case you can use additional flag for create a project from current Sophos code warehouse in Azure DevOps.

1. Run thothctl for reusing.

```commandline
$  thothctl init --project_name myproject -reuse   --org_name sophosproyectos

```
![Reuse init project](img/reuse_project_pattern.gif)

