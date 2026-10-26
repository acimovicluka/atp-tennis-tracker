# the actual things terraform creates on aws:
# an ssh key, a firewall and the server itself


# finds the newest ubuntu 24.04 image instead of hardcoding an id
# image ids are different in every region and change with every update
# "data" means terraform only looks this up, it doesn't create anything
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]   # canonical, the company behind ubuntu

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }
}


# uploads my public ssh key to aws so the server lets me in
resource "aws_key_pair" "atp" {
  key_name   = "atp-tracker"
  public_key = file(pathexpand(var.public_key_path))   # pathexpand turns ~ into the real home folder
}


# firewall for the server, aws calls it a security group
# by default everything coming in is blocked, so each rule below opens one port
resource "aws_security_group" "atp" {
  name        = "atp-tracker"
  description = "ssh and the api"

  # port 22 so I can log in over ssh, ansible uses it too
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.ssh_allowed_cidr]
  }

  # port 8000 is the api, open to everyone so it works from any browser
  ingress {
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # the server itself can reach anything outside
  # it needs this to install docker and to download the match data
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"   # -1 means every protocol
    cidr_blocks = ["0.0.0.0/0"]
  }
}


# the server
# everything above gets plugged in here, which is how terraform knows to create them first
resource "aws_instance" "atp" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  key_name               = aws_key_pair.atp.key_name
  vpc_security_group_ids = [aws_security_group.atp.id]

  # the disk, 20 GB leaves enough room for docker images and the database
  root_block_device {
    volume_size = 20
    volume_type = "gp3"
  }

  # the name that shows up in the aws console
  tags = {
    Name = "atp-tracker"
  }
}


# writes the ansible inventory with the ip of the new server
# this way I never have to copy the ip by hand after terraform apply
# the file is made from inventory.tftpl, terraform only fills in the ip
resource "local_file" "inventory" {
  filename = "${path.module}/../ansible/inventory.ini"   # path.module is this terraform folder
  content = templatefile("${path.module}/inventory.tftpl", {
    ip = aws_instance.atp.public_ip
  })
}
