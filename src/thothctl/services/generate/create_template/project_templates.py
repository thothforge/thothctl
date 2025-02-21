"""Define project templates."""
terraform_template = [
    {
        "type": "directory",
        "name": ".",
        "contents": [
            {"type": "file", "name": "README.md"},
            {"type": "file", "name": "root.hcl"},
            {"type": "file", "name": ".tflint.hcl"},
            {"type": "file", "name": ".gitignore"},
            {"type": "file", "name": ".pre-commit-config.yaml"},
            {"type": "file", "name": ".thothcf.toml"},
            {
                "type": "directory",
                "name": "common",
                "contents": [
                    {"type": "file", "name": "common.hcl"},
                    {"type": "file", "name": "common.tfvars"},
                    {"type": "file", "name": "variables.tf"},
                ],
            },
            {
                "type": "directory",
                "name": "docs",
                "contents": [
                    {"type": "file", "name": "DiagramArchitecture.png"},
                    {"type": "file", "name": "graph.svg"},
                ],
            },
            {
                "type": "directory",
                "name": "resources",
                "contents": [
                    {
                        "type": "directory",
                        "name": "compute",
                        "contents": [
                            {
                                "type": "directory",
                                "name": "EC2",
                                "contents": [
                                    {
                                        "type": "directory",
                                        "name": "ALB_Main",
                                        "contents": [
                                            {"type": "file", "name": "README.md"},
                                            {"type": "file", "name": "graph.svg"},
                                            {"type": "file", "name": "main.tf"},
                                            {"type": "file", "name": "outputs.tf"},
                                            {
                                                "type": "file",
                                                "name": "parameters.tf",
                                            },
                                            {
                                                "type": "file",
                                                "name": "terragrunt.hcl",
                                            },
                                            {
                                                "type": "file",
                                                "name": "variables.tf",
                                            },
                                        ],
                                    }
                                ],
                            }
                        ],
                    }
                ],
            },
        ],
    }
]

terraform_module_template = [
    {
        "type": "directory",
        "name": ".",
        "contents": [
            {"type": "file", "name": "README.md"},
            {"type": "file", "name": ".gitignore"},
            {"type": "file", "name": ".pre-commit-config.yaml"},
            {"type": "file", "name": ".thothcf.toml"},
            {"type": "file", "name": "main.tf"},
            {"type": "file", "name": "outputs.tf"},
            {"type": "file", "name": "variables.tf"},
            {"type": "file", "name": "README.md"},
            {
                "type": "directory",
                "name": "modules",
                "contents": [
                    {"type": "file", "name": "main.tf"},
                    {"type": "file", "name": "outputs.tf"},
                    {"type": "file", "name": "variables.tf"},
                    {"type": "file", "name": "README.md"},
                ],
            },
            {
                "type": "directory",
                "name": "docs",
                "contents": [
                    {"type": "file", "name": "DiagramArchitecture.png"},
                    {"type": "file", "name": "graph.svg"},
                ],
            },
            {
                "type": "directory",
                "name": "examples",
                "contents": [
                    {
                        "type": "directory",
                        "name": "complete",
                        "contents": [
                            {"type": "file", "name": "README.md"},
                            {"type": "file", "name": "variables.tf"},
                            {"type": "file", "name": "main.tf"},
                            {"type": "file", "name": "outputs.tf"},
                        ],
                    }
                ],
            },
        ],
    }
]
