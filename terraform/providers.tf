# tells terraform which plugins it needs before it can do anything
# terraform itself knows nothing about aws, the aws provider is the part that talks to it
terraform {
  required_version = ">= 1.16"   # stops anyone with an older terraform from running this

  required_providers {
    aws = {
      source  = "hashicorp/aws"   # the official aws provider from the terraform registry
      version = "~> 6.0"          # any 6.x version is fine, but it never jumps to 7 on its own
    }

    # writes files on my own computer, used for the ansible inventory
    local = {
      source  = "hashicorp/local"
      version = "~> 2.5"
    }
  }
}

# settings for the aws provider
# it logs in with the same keys as the aws cli, so there are no passwords here
provider "aws" {
  region = var.region
}
