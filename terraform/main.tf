# these are the actual things terraform creates on aws: an ssh key, a firewall and the server itself
# plus the ansible inventory file on my computer
# terraform apply creates them, terraform destroy deletes all of them again
# terraform keeps track of what it made in terraform.tfstate, which stays only on my computer


# this looks up the newest ubuntu 24.04 image (AMI), instead of writing an image id by hand
# image ids are different in every region and change with every ubuntu update
# "data" means terraform only reads this from aws, it doesn't create anything
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]   # canonical, the company behind ubuntu, so terraform only picks official images

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]   # noble is the name of ubuntu 24.04
  }
}


# terraform uploads my public ssh key to aws, so the new server lets me (and ansible) log in
resource "aws_key_pair" "atp" {
  key_name   = "atp-tracker"
  public_key = file(pathexpand(var.public_key_path))   # pathexpand turns ~ into the real home folder, file reads the key
}


# the firewall for the server, aws calls it a security group
# aws blocks everything coming in by default, so each ingress rule below opens one port
resource "aws_security_group" "atp" {
  name        = "atp-tracker"
  description = "ssh and the api"

  # port 22 for ssh, so I can log in, and ansible uses it too
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

  # port 3000 is grafana, the page with the charts, open to everyone like the api
  ingress {
    from_port   = 3000
    to_port     = 3000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # egress is the traffic going out: the server itself can reach anything on the internet
  # it needs this to install git and k3s, pull the images from GHCR and download the match data
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"   # -1 means every protocol
    cidr_blocks = ["0.0.0.0/0"]
  }
}


# the server itself (an EC2 instance)
# everything above gets plugged in here, and that's how terraform knows it has to create those first
resource "aws_instance" "atp" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  key_name               = aws_key_pair.atp.key_name
  vpc_security_group_ids = [aws_security_group.atp.id]

  # the disk, 20 GB leaves enough room for the container images and the database
  root_block_device {
    volume_size = 20
    volume_type = "gp3"
  }

  # the name that shows up in the aws console
  tags = {
    Name = "atp-tracker"
  }
}


# terraform writes the ansible inventory with the ip of the new server
# every apply makes a new server with a new ip, and this way I never have to copy the ip by hand
# terraform takes inventory.tftpl as a template and only fills in the ip
resource "local_file" "inventory" {
  filename = "${path.module}/../ansible/inventory.ini"   # path.module is this terraform folder, so the file lands in ansible/
  content = templatefile("${path.module}/inventory.tftpl", {
    ip = aws_instance.atp.public_ip
  })
}
