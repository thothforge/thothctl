"""Define Files contents for template."""
# TODO UPGRADE to latest version to manage workspaces
terragrunt_hcl_content = """
include "root" {
  path = find_in_parent_folders("root.hcl")
  expose = true
}
"""
terragrunt_root_hcl_content = """locals {
  common_vars = read_terragrunt_config("${get_parent_terragrunt_dir()}/common/common.hcl")
}

inputs = {
  COMMAND        = get_terraform_cli_args()
  COMMAND_GLOBAL = local.common_vars.locals
}

terraform {
  extra_arguments "init_arg" {
    commands  = ["init"]
    arguments = [
      "-reconfigure"
    ]
    env_vars = {
      TERRAGRUNT_AUTO_INIT = true

    }
  }

  extra_arguments "common_vars" {
    commands = get_terraform_commands_that_need_vars()

    arguments = [
      "-var-file=${get_parent_terragrunt_dir()}/common/common.tfvars"

    ]
  }

  after_hook "sync_workspace" {
    commands = ["workspace"]
    execute  = [
      "thothctl", "--sync_terraform_workspaces",

    ]

  }

  before_hook "sync_workspaces" {
    commands = ["plan", "apply", "destroy", "refresh", "state"]
    execute  = [
      "thothctl", "--sync_terraform_workspaces",

    ]

  }


}


remote_state {
  backend = "s3"
  generate = {
    path      = "remotebackend.tf"
    if_exists = "overwrite"
  }
  config = {
    bucket               = local.common_vars.locals.backend_bucket_name
    profile              = local.common_vars.locals.backend_profile
    region               = local.common_vars.locals.backend_region
    workspace_key_prefix = "${local.common_vars.locals.project_folder}/${path_relative_to_include()}"
    key                  = local.common_vars.locals.backend_key
    encrypt              = local.common_vars.locals.backend_encrypt
    dynamodb_table       = "${local.common_vars.locals.backend_dynamodb_lock}-${local.common_vars.locals.project}"
  }
}

generate = local.common_vars.generate


"""
terragrunt_hcl_clean = """locals {
  common_vars = read_terragrunt_config("${get_parent_terragrunt_dir()}/common/common.hcl")
}

inputs = {
  COMMAND        = get_terraform_cli_args()
  COMMAND_GLOBAL = local.common_vars.locals
}

terraform {
  extra_arguments "init_arg" {
    commands  = ["init"]
    arguments = [
      "-reconfigure"
    ]
    env_vars = {
      TERRAGRUNT_AUTO_INIT = true

    }
  }

  extra_arguments "common_vars" {
    commands = get_terraform_commands_that_need_vars()

    arguments = [
      "-var-file=${get_parent_terragrunt_dir()}/common/common.tfvars"

    ]
  }

}


remote_state {
  backend = "s3"
  generate = {
    path      = "remotebackend.tf"
    if_exists = "overwrite"
  }
  config = {
    bucket               = local.common_vars.locals.backend_bucket_name
    profile              = local.common_vars.locals.backend_profile
    region               = local.common_vars.locals.backend_region
    workspace_key_prefix = "${local.common_vars.locals.project_folder}/${path_relative_to_include()}"
    key                  = local.common_vars.locals.backend_key
    encrypt              = local.common_vars.locals.backend_encrypt
    dynamodb_table       = "${local.common_vars.locals.backend_dynamodb_lock}-${local.common_vars.locals.project}"
  }
}

generate = local.common_vars.generate


"""


common_tfvars_content = """
# Default values for deployment credentials
# Access profile in your IDE env or pipeline the IAM user to use for deployment."
profile = {
      default = {
        profile = "#{deployment_profile}#"
        region = "#{deployment_region}#"
  }
      dev  = {
        profile = "#{deployment_profile}#"
        region = "#{deployment_region}#"
  }
      prod = {
        profile = "#{deployment_profile}#"
        region = "#{deployment_region}#"
  }
}

# Project default tags
project = "#{project_name}#"
required_tags = {
    ManagedBy = "Terraform-Terragrunt"
    Project = "#{project_name}#"

}
"""
variables_tf_content = """# General variables
variable "profile" {
  type = map(any)
  description = "Access profile for the IAM user to use for deployment."
  default     = {
    default = {
      profile = "default_profile"
      region  = "us-east-2"
    }
    dev = {
      profile = "default_profile"
      region  = "us-east-2"
    }
    prod = {
      profile = "default_profile"
      region  = "us-east-2"
    }
  }

}

variable "project" {
  type        = string
  description = "Project tool"
}

variable "required_tags" {
  description = "A map of tags to add to all resources"
  type        = map(string)
  default     = {}
}

variable "provider" {
  type        = string
  default     = "AWS"
  description = "Cloud Provider, for example: aws, azure, gcp"
}

variable "client" {
  type        = string
  default     = "internal"
  description = "Client Name"
}

"""
common_hcl_content = """# Load variables in locals
# Load variables in locals
locals {
  # Default values for variables
  profile           = "#{deployment_profile}#"
  project           = "#{project_name}#"
  deployment_region = "#{deployment_region}#"
  provider          = "#{cloud_provider}#"
  client = "#{client}#"

  # Set tags according to company policies
  tags = {
    ProjectCode = "#{project_code}#"
    Framework   = "DevSecOps-IaC"
  }

  # Backend Configuration
  backend_region        = "#{backend_region}#"
  backend_bucket_name   = "#{backend_bucket}#"
  backend_profile       = "#{backend_profile}#"
  backend_dynamodb_lock = "#{backend_dynamodb}#"
  backend_key           = "terraform.tfstate"
  backend_encrypt = true
  # format cloud provider/client/projectname
  project_folder        = "${local.provider}/${local.client}/${local.project}"

}

generate "provider" {
  path      = "provider.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<EOF
variable "required_tags" {
  description = "A map of tags to add to all resources"
  type        = map(string)
  default     = {}
}
variable "project" {
  type        = string
  description = "Project tool"
}
variable "profile" {
  description = "Variable for credentials management."
  default = {
    default = {
      profile = "#{deployment_profile}#"
      region = "#{deployment_region}#"
}
    dev  = {
      profile = "#{deployment_profile}#"
      region = "#{deployment_region}#"
}
    prod = {
      profile = "#{deployment_profile}#"
      region = "#{deployment_region}#"
    
}
  }

}


provider "aws" {
  region  = var.profile[terraform.workspace]["region"]
  profile = var.profile[terraform.workspace]["profile"]

  default_tags {
    tags = var.required_tags

}
}

EOF
}


EOF
}
"""
tflint_hcl = """
plugin "aws" {
    enabled = true
    version = "0.21.1"
    source  = "github.com/terraform-linters/tflint-ruleset-template"
}
config {
  module = true
}

plugin "terraform" {
    enabled = true
    version = "0.2.2"
    source  = "github.com/terraform-linters/tflint-ruleset-terraform"
}
"""
git_ignore = """

**/tfplan
**/builds
**/backend.tf
**/remotebackend.tf
**/provider.tf
#exlude reports
Reports/*

#Exclude terramate file
**/terramate.tm.hcl

# Created by https://www.toptal.com/developers/gitignore/api/terraform,terragrunt,pycharm,visualstudiocode
# Edit at https://www.toptal.com/developers/gitignore?templates=terraform,terragrunt,pycharm,visualstudiocode

### PyCharm ###
# Covers JetBrains IDEs: IntelliJ, RubyMine, PhpStorm, AppCode, PyCharm, CLion, Android Studio, WebStorm and Rider
# Reference: https://intellij-support.jetbrains.com/hc/en-us/articles/206544839

# User-specific stuff
.idea/**/workspace.xml
.idea/**/tasks.xml
.idea/**/usage.statistics.xml
.idea/**/dictionaries
.idea/**/shelf

# AWS User-specific
.idea/**/aws.xml

# Generated files
.idea/**/contentModel.xml

# Sensitive or high-churn files
.idea/**/dataSources/
.idea/**/dataSources.ids
.idea/**/dataSources.local.xml
.idea/**/sqlDataSources.xml
.idea/**/dynamic.xml
.idea/**/uiDesigner.xml
.idea/**/dbnavigator.xml

# Gradle
.idea/**/gradle.xml
.idea/**/libraries

# Gradle and Maven with auto-import
# When using Gradle or Maven with auto-import, you should exclude module files,
# since they will be recreated, and may cause churn.  Uncomment if using
# auto-import.
# .idea/artifacts
# .idea/compiler.xml
# .idea/jarRepositories.xml
# .idea/modules.xml
# .idea/*.iml
# .idea/modules
# *.iml
# *.ipr

# CMake
cmake-build-*/

# Mongo Explorer plugin
.idea/**/mongoSettings.xml

# File-based project format
*.iws

# IntelliJ
out/

# mpeltonen/sbt-idea plugin
.idea_modules/

# JIRA plugin
atlassian-ide-plugin.xml

# Cursive Clojure plugin
.idea/replstate.xml

# SonarLint plugin
.idea/sonarlint/

# Crashlytics plugin (for Android Studio and IntelliJ)
com_crashlytics_export_strings.xml
crashlytics.properties
crashlytics-build.properties
fabric.properties

# Editor-based Rest Client
.idea/httpRequests

# Android studio 3.1+ serialized cache file
.idea/caches/build_file_checksums.ser

### PyCharm Patch ###
# Comment Reason: https://github.com/joeblau/gitignore.io/issues/186#issuecomment-215987721

# *.iml
# modules.xml
# .idea/misc.xml
# *.ipr

# Sonarlint plugin
# https://plugins.jetbrains.com/plugin/7973-sonarlint
.idea/**/sonarlint/

# SonarQube Plugin
# https://plugins.jetbrains.com/plugin/7238-sonarqube-community-plugin
.idea/**/sonarIssues.xml

# Markdown Navigator plugin
# https://plugins.jetbrains.com/plugin/7896-markdown-navigator-enhanced
.idea/**/markdown-navigator.xml
.idea/**/markdown-navigator-enh.xml
.idea/**/markdown-navigator/

# Cache file creation bug
# See https://youtrack.jetbrains.com/issue/JBR-2257
.idea/$CACHE_FILE$

# CodeStream plugin
# https://plugins.jetbrains.com/plugin/12206-codestream
.idea/codestream.xml

# Azure Toolkit for IntelliJ plugin
# https://plugins.jetbrains.com/plugin/8053-azure-toolkit-for-intellij
.idea/**/azureSettings.xml

### Terraform ###
# Local .terraform directories
**/.terraform/*

# .tfstate files
*.tfstate
*.tfstate.*

# Crash log files
crash.log
crash.*.log

# Exclude all .tfvars files, which are likely to contain sensitive data, such as
# password, private keys, and other secrets. These should not be part of version
# control as they are data points which are potentially sensitive and subject
# to change depending on the environment.
*.tfvars
*.tfvars.json

# Ignore override files as they are usually used to override resources locally and so
# are not checked in
override.tf
override.tf.json
*_override.tf
*_override.tf.json

# Include override files you do wish to add to version control using negated pattern
# !example_override.tf

# Include tfplan files to ignore the plan output of command: terraform plan -out=tfplan
# example: *tfplan*

# Ignore CLI configuration files
.terraformrc
terraform.rc

### Terragrunt ###
# terragrunt cache directories
**/.terragrunt-cache/*

# Terragrunt debug output file (when using `--terragrunt-debug` option)
# See: https://terragrunt.gruntwork.io/docs/reference/cli-options/#terragrunt-debug
terragrunt-debug.tfvars.json

### VisualStudioCode ###
.vscode/*
!.vscode/settings.json
!.vscode/tasks.json
!.vscode/launch.json
!.vscode/extensions.json
!.vscode/*.code-snippets

# Local History for Visual Studio Code
.history/

# Built Visual Studio Code Extensions
*.vsix

### VisualStudioCode Patch ###
# Ignore all local history of files
.history
.ionide

# End of https://www.toptal.com/developers/gitignore/api/terraform,terragrunt,pycharm,visualstudiocode


"""
parameters_tf_content = """
locals {
  env = {
    default = {
      create = true
    }
    "#{environment}#" = {
      create = true
    }

  }
  environment_vars = contains(keys(local.env), terraform.workspace) ? terraform.workspace : "default"
  workspace        = merge(local.env["default"], local.env[local.environment_vars])
}
"""
terragrunt_hcl_resource_content = """
include "root" {
  path = find_in_parent_folders("root")
} 
"""
main_tf_content = """
/*
* # Module for #{resource_name}# deployment
*
* Terraform stack to provision a custom #{resource_name}#
*
*/
"""
pre_commit_content = """
repos:
#  - repo: https://github.com/antonbabenko/pre-commit-terraform
#    rev: v1.88.4  # Get the latest from: https://github.com/antonbabenko/pre-commit-terraform/releases
#    hooks:
#      # args: ["--output-file", "README.md"]
#      - id: terraform_tfsec
#      - id: terraform_checkov
#      - id: terraform_fmt
#        args:
#          - --args=-no-color
#          - --args=-diff
#          - --args=-write=true

- repo: https://github.com/gruntwork-io/pre-commit
  rev: v0.1.23 # Get the latest from: https://github.com/gruntwork-io/pre-commit/releases
  hooks:
    - id: terragrunt-hclfmt
    - id: terraform-fmt
    - id: terraform-validate
    - id: tflint
    - id: shellcheck
    - id: gofmt
    - id: golint
"""
thothcf_toml_content = """#conf
[template_input_parameters.project_name]
template_value = "#{project_name}#"
condition = "\\\b[a-zA-Z]+\\\b"
description = "Project Name"

[template_input_parameters.deployment_region]
template_value = "#{deployment_region}#"
condition = "^[a-z]{2}-[a-z]{4,10}-\\\d$"
description = "Aws Region"

[template_input_parameters.backend_bucket]
template_value = "#{backend_bucket}#"
condition = "^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$"
description = "Backend Bucket for tfstate"

[template_input_parameters.backend_region]
template_value = "#{backend_region}#"
condition = "^[a-z]{2}-[a-z]{4,10}-\\\d$"
description = "Backend Aws Region"

[template_input_parameters.owner]
template_value = "#{owner}#"
condition = "\\\b[a-zA-Z]+\\\b"
description = "Team or role owner for this deployment"

[template_input_parameters.client]
template_value = "#{client}#"
condition = "\\\b[a-zA-Z]+\\\b"
description = "Client or Area for this deployment"

[template_input_parameters.backend_dynamodb]
template_value = "#{backend_dynamodb}#"
condition = "^[a-zA-Z0-9_.-]{3,255}$"
description = "Dynamodb for lock state"

[template_input_parameters.environment]
template_value = "#{environment}#"
condition = "(dev|qa|stg|test|prod)"
description = "The environment or workspace name for initial setup. Environment allowed values (dev|qa|stg|test|prod)"

[template_input_parameters.cloud_provider]
template_value = "#{cloud_provider}#"
condition = "(aws|azure|oci|gcp)"
description = "The environment or workspace name for initial setup. Environment allowed values (aws|azure|oci|gcp)"


[template_input_parameters.deployment_profile]
template_value = "#{deployment_profile}#"
condition = "^[a-zA-Z0-9_.-]{3,255}$"
description = "Deployment profile aws cli"

[template_input_parameters.backend_profile]
template_value = "#{backend_profile}#"
condition = "^[a-zA-Z0-9_.-]{3,255}$"
description = "Backend profile for s3 remote state"
"""

thothcf_toml_module_content = """
# Define template input parameters
[template_input_parameters.module_name]
template_value = "#{ModuleName}#"
condition = "^[a-z_]+$"
description = "Module Name"

[template_input_parameters.resources_to_create]
template_value= "#{ResourcesToCreate}#"
condition= "^[a-zA-Z\\\s]+$"
description = "Resources to create in this module"

[template_input_parameters.description]
template_value= "#{ModuleDescription}#"
condition = "^[a-zA-Z\\\s]+$"
description = "Module description"

# Define project structure
[project_structure]
root_files = [
   ".git",
    ".gitignore",
    ".pre-commit-config.yaml",
    "README.md"
]
ignore_folders = [
    ".git",
    ".terraform",
    "Reports"
]

[[project_structure.folders]]
name = "catalog"
mandatory = false
content = [
    "catalog-info.yaml",
    "mkdocs.yaml"
]
type= "child_folder"
[[project_structure.folders]]
name = "docs"
mandatory = true
type= "root"
[[project_structure.folders]]
name = "modules"
mandatory = false
content = [
    "variables.tf",
    "main.tf",
    "outputs.tf",
    "README.md"
]
type= "root"
[[project_structure.folders]]
name = "examples"
mandatory = true
type= "root"
content = [
    "main.tf",
    "outputs.tf",
    "terraform.tfvars",
    "README.md",
    "variables.tf",
]
[[project_structure.folders]]
name = "test"
mandatory = false
# Set rule for root file


"""
