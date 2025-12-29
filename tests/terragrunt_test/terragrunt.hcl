terraform {
  source = "tfr:///terraform-aws-modules/alb/aws?version=8.7.0"
}

inputs = {
  create_lb          = true
  name               = "test-alb"
  vpc_id             = "vpc-12345"
  load_balancer_type = "application"
  internal           = true
}
