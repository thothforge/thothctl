# Quick Start

## Installation

### Universal Installation (All Platforms)

```bash
pip install thothctl
```

### Platform-Specific Guides

- **Windows**: [Windows Installation Guide](installation/windows_installation.md)
- **Linux**: Standard pip installation works on all distributions
- **macOS**: Standard pip installation with Homebrew support

### Verify Installation

```bash
thothctl --version
```

## Setup Autocomplete

Enable command autocompletion for your shell:

```bash
# All platforms
thothctl-register-autocomplete
```

This will configure:
- **PowerShell** autocomplete on Windows
- **Bash/Zsh/Fish** autocomplete on Linux/macOS

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
  check      Validate environment, IaC, cost analysis, and blast radius
  document   Generate documentation for IaC projects with AI support
  generate   Generate IaC from rules, use cases, and components
  init       Initialize and setup project configurations and environments
  inventory  Create inventory for IaC composition with version tracking
  list       List projects and spaces managed by thothctl locally
  mcp        Model Context Protocol (MCP) server for AI integration
  project    Convert, clean up and manage the current project
  remove     Remove projects and spaces managed by thothctl
  scan       Scan infrastructure code for security issues and compliance
  upgrade    Upgrade thothctl to the latest version
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


> Just support Azure DevOps and Github Integration - We're working for more integrations 👷


#### Create project from void template

You can create a project without content, just a void template with base structure. For example:

```commandline
$  thothctl init project --project-name <project_name>

```

#### Create a new project based on existing templates
> You must have a Personal Access Token for list the projects.

1. Run thothctl for reusing a project or template.

```commandline
$  thothctl init --project_name myproject -reuse --space lab-github

```
For example: 
```bash
$ thothctl init project -reuse -s lab-github -pj ecs_pro

ℹ️ 🚀 Initializing project: ecs_pro
ℹ️ 🌌 Using space: lab-github
ℹ️ 🔗 Using VCS provider from space: github
INFO - Initializing project: ecs_pro
INFO - Project ecs_pro initialized successfully
ℹ️ 🔄 Setting up Github integration...
ERROR - Credentials file not found: /home/labvel/.thothcf/spaces/lab-github/credentials/vcs.enc
WARNING - Failed to load credentials from space 'lab-github': Credentials file not found: /home/labvel/.thothcf/spaces/lab-github/credentials/vcs.enc
ℹ️ GitHub Personal Access Token required
Enter your GitHub Personal Access Token:
Enter GitHub username or organization name: velez94
Establishing GitHub connection...

Patterns available:
[?]  Select a pattern to reuse:  🔍 :
   cdkv2_manage_identity_center_template
   terragrunt_aws_gitops_blueprint
   terragrunt_aws_gitops_spoke_blueprint
 > terragrunt_ecs_blueprint


The pattern is:
terragrunt_ecs_blueprint ➡️ https://github.com/velez94/terragrunt_ecs_blueprint.git
✨ Cloning repository
No tags found. Using main branch.
❗ Clean up metadata ...
✨ Template is almost ready for project ecs_pro 🧑🏽‍💻!

 Write project parameters for ecs_pro
[?] Input Project Name : test-ecs
[?] Input Aws Region : us-east-1
[?] Input Backend Aws Region : us-east-1
[?] Input Backend Bucket : bucket
[?] Input Deployment Owner : lab
[?] Input Dynamodb for lock state : db-lock
[?] Input Environment allowed values (dev|qa|stg|test|prod) : dev
[?] Input Deployment profile aws cli : lab-dev
[?] Input Backend profile for s3 remote state : lab-dev
👷 Parsing template ...
👷 Modifying README.md for ecs_pro
INFO - Updating project info ecs_pro
👷 Modifying README.md for ecs_pro
INFO - Updating project info ecs_pro
INFO - Doesn't exists {'source': 'infrastructure/Network/VPC', 'local': 'README.md', 'hash': '4014f00b531e0f9783752f6e30a33887ed036c51a58c797a6e4e4964a9e48631'}
👷 Modifying terragrunt.hcl for ecs_pro
INFO - Updating project info ecs_pro
INFO - Doesn't exists {'source': 'infrastructure/Network/VPC', 'local': 'terragrunt.hcl', 'hash': 'd17f6d45792178c516489fb9585c2a0546900848576b5073facd7beed8a98894'}
👷 Modifying README.md for ecs_pro
INFO - Updating project info ecs_pro
INFO - Doesn't exists {'source': 'infrastructure/Network/SecurityGroups/ALB', 'local': 'README.md', 'hash': '5fc750699c9828c802fc3112b6bd7cbfadc0b2ba1b45cf61943752cf68785f81'}
👷 Modifying terragrunt.hcl for ecs_pro
INFO - Updating project info ecs_pro
INFO - Doesn't exists {'source': 'infrastructure/Network/SecurityGroups/ALB', 'local': 'terragrunt.hcl', 'hash': 'fcb649c8ab10c1b5c4084f53dc4fc03a87978e6df5bf2a07f9bd50c4d5c8a4ec'}
👷 Modifying README.md for ecs_pro
INFO - Updating project info ecs_pro
INFO - Doesn't exists {'source': 'infrastructure/Network/SecurityGroups/ECS/SampleService', 'local': 'README.md', 'hash': 'b3fb73cc6a98948902c4e41ca7f01ff39d91197e653a2cd09cc50eee2f00ba6e'}
👷 Modifying terragrunt.hcl for ecs_pro
INFO - Updating project info ecs_pro
INFO - Doesn't exists {'source': 'infrastructure/Network/SecurityGroups/ECS/SampleService', 'local': 'terragrunt.hcl', 'hash': 'fb64a80c871ff49e78cbcf915116c2a6e0ea5224c9a2b55877901f887ef9f768'}
👷 Modifying README.md for ecs_pro
INFO - Updating project info ecs_pro
INFO - Doesn't exists {'source': 'infrastructure/Compute/ALB', 'local': 'README.md', 'hash': 'eba4400ee12fee4c6939f5f8ce90ab671a73c110bb1830affa4ac64758462622'}
👷 Modifying terragrunt.hcl for ecs_pro
INFO - Updating project info ecs_pro
INFO - Doesn't exists {'source': 'infrastructure/Compute/ALB', 'local': 'terragrunt.hcl', 'hash': 'd5ce60e24e77fab7f968f88c9a6fd2666ef08b8fc4d65a94bf974e06774f9a0c'}
👷 Modifying README.md for ecs_pro
INFO - Updating project info ecs_pro
INFO - Doesn't exists {'source': 'infrastructure/Containers/ECSCluster', 'local': 'README.md', 'hash': 'ac9b8a965590d6d017fa4d2b47b78d775933d3c476fb2d4857b3ef668981959d'}
👷 Modifying terragrunt.hcl for ecs_pro
INFO - Updating project info ecs_pro
INFO - Doesn't exists {'source': 'infrastructure/Containers/ECSCluster', 'local': 'terragrunt.hcl', 'hash': '4c7c853b3b8907a36f3fba132894507b8c81ed5c9d3432a34d318a3cc0777f6d'}
👷 Modifying README.md for ecs_pro
INFO - Updating project info ecs_pro
INFO - Doesn't exists {'source': 'infrastructure/Containers/ECSServices/SampleService', 'local': 'README.md', 'hash': '8945a52198570eed59dff9956c178492cdb07584dbeabb9a71e3b4d73d5a86e1'}
👷 Modifying terragrunt.hcl for ecs_pro
INFO - Updating project info ecs_pro
INFO - Doesn't exists {'source': 'infrastructure/Containers/ECSServices/SampleService', 'local': 'terragrunt.hcl', 'hash': 'e11f989adee9bf06fae3fcf3967d588cff070cb9bc415401ff21cfb30d5f2fa1'}
👷 Modifying README.md for ecs_pro
INFO - Updating project info ecs_pro
INFO - Doesn't exists {'source': 'infrastructure/Operations/ResourceGroup', 'local': 'README.md', 'hash': 'a9fc5425049235215c0d7a23ac890b59c284d6049f32cf2a0b393bdab9b3f123'}
👷 Modifying terragrunt.hcl for ecs_pro
INFO - Updating project info ecs_pro
INFO - Doesn't exists {'source': 'infrastructure/Operations/ResourceGroup', 'local': 'terragrunt.hcl', 'hash': 'd3f392dff60eb9a5176c6bc78169af18c079cdea29b907ae88bf5c134bc4303a'}
👷 Modifying common.tfvars for ecs_pro
INFO - Updating project info ecs_pro
INFO - Doesn't exists {'source': 'common', 'local': 'common.tfvars', 'hash': 'c28447d3ea0f18066c61558fe697d6233c1258d7de3db88aa6e4b0b116e8f932'}
👷 Modifying environment.hcl for ecs_pro
INFO - Updating project info ecs_pro
INFO - Doesn't exists {'source': 'common', 'local': 'environment.hcl', 'hash': '9fe64823556e09ce085d398f7b951eec6d6d93c1b16f9a4ffdcaa8ff5e2e99db'}
👷 Modifying common.hcl for ecs_pro
INFO - Updating project info ecs_pro
INFO - Doesn't exists {'source': 'common', 'local': 'common.hcl', 'hash': 'aa58f57d1cf9aab120ec6b7bbd6a8549877f2f94be61ae111ce0549ca7b6c166'}
✅ Done!
INFO -  Opening <_io.TextIOWrapper name='./.thothcf.toml' mode='a' encoding='UTF-8'> ...
 catalog-info.yaml file created in docs/catalog//catalog-info.yaml.
✅ ✨ Project 'ecs_pro' initialized successfully!
```

Now open code in your favorite IDE 🔨.

