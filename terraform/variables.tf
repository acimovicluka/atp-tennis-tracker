# everything that might change from one run to another lives here as a variable
# main.tf only uses var.something, so changing a value means changing it in one place
# each variable has a default, and a terraform.tfvars file could change it without touching the code


# which aws region terraform creates the server in
variable "region" {
  type    = string
  default = "eu-north-1"   # stockholm, the same region my aws cli uses
}

# how big the server is
# t3.small has 2 cpus and 2 GB of ram
# kubernetes (k3s) takes about half a gig by itself, so the 1 GB t3.micro I started with is too small now
variable "instance_type" {
  type    = string
  default = "t3.small"
}

# the public half of the ssh key that lets me log into the server
# terraform uploads it to aws, the private half stays on my computer and never goes anywhere
# ~ means my home folder, so on windows this is C:\Users\Luka\.ssh
variable "public_key_path" {
  type    = string
  default = "~/.ssh/atp-tracker.pub"
}

# which ip addresses the firewall lets in over ssh, written as a cidr range
# 0.0.0.0/0 means any address, but nobody gets in without my private key, so it's not wide open
# I could lock it down to just my own ip later, but then the Deploy workflow on github couldn't get in
variable "ssh_allowed_cidr" {
  type    = string
  default = "0.0.0.0/0"
}
