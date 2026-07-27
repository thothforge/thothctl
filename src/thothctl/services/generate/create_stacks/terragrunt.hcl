include "root" {
  path = find_in_parent_folders("root.hcl")
}

include "env" {
  path = find_in_parent_folders("env.hcl")
}

dependency "vpc" {
  config_path = "${get_parent_terragrunt_dir()}/vpc"

  mock_outputs = {
    vpc_id = "vpc-12345678"
    private_subnets = ["subnet-12345678"]
  }

  mock_outputs_merge_strategy_with_state = "shallow"
}

dependency "security_groups" {
  config_path = "${get_parent_terragrunt_dir()}/security-groups"

  mock_outputs = {
    bastion_sg_id = ["sg-12345678"]
  }

  mock_outputs_merge_strategy_with_state = "shallow"
}

inputs = {
  master_user_secret_kms_key_id = dependency.vpc.outputs.vpc_id
  vpc_security_group_ids = dependency.vpc.outputs.vpc_id
  performance_insights_kms_key_id = dependency.vpc.outputs.vpc_id
  kms_key_id = dependency.vpc.outputs.vpc_id
  cloudwatch_log_group_kms_key_id = dependency.vpc.outputs.vpc_id
}
