# everything that might change from one run to another lives here
# main.tf only uses var.something, so changing a value means changing it in one place


# which aws region the server goes to
variable "region" {
  type    = string
  default = "eu-north-1"   # stockholm, same region as my aws cli
}

# how big the server is
# t3.micro is 2 cpus and 1 GB of ram, enough for postgres, the fetcher and the api
variable "instance_type" {
  type    = string
  default = "t3.micro"
}

# the public half of the ssh key that lets me log into the server
# the private half stays on my computer and never goes anywhere
# ~ means my home folder, so on windows this is C:\Users\Luka\.ssh
variable "public_key_path" {
  type    = string
  default = "~/.ssh/atp-tracker.pub"
}

# which addresses are allowed to connect over ssh
# 0.0.0.0/0 means anyone, the key is still needed so it's not wide open
# can be locked down to just my own ip later
variable "ssh_allowed_cidr" {
  type    = string
  default = "0.0.0.0/0"
}
