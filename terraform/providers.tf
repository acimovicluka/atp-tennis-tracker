# this file tells terraform which plugins (providers) it needs before it can do anything
# terraform itself knows nothing about aws, the aws provider is the part that actually talks to aws
# terraform init reads this file and downloads the providers into the .terraform folder
terraform {
  required_version = ">= 1.16"   # terraform stops anyone with an older version from running this

  required_providers {
    aws = {
      source  = "hashicorp/aws"   # the official aws provider from the terraform registry
      version = "~> 6.0"          # any 6.x version is fine, but terraform never jumps to 7 on its own (7 could break things)
    }

    # the local provider writes files on my own computer, main.tf uses it for the ansible inventory
    local = {
      source  = "hashicorp/local"
      version = "~> 2.5"
    }
  }
}

# settings for the aws provider
# it logs in with the same access keys as the aws cli (from ~/.aws/credentials), so there are no passwords in this file
provider "aws" {
  region = var.region
}
