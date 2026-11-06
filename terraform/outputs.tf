# outputs are the things terraform prints at the end of terraform apply
# the ip changes every time terraform creates the server again, so this saves me looking it up in the aws console
# terraform output prints them again later, without changing anything


# the public ip of the server, I paste this into the Deploy workflow on github
output "public_ip" {
  value = aws_instance.atp.public_ip
}

# the full address of the api docs, ready to paste into the browser
output "api_url" {
  value = "http://${aws_instance.atp.public_ip}:8000/docs"
}

# the command for logging into the server over ssh
output "ssh_command" {
  value = "ssh -i ~/.ssh/atp-tracker ubuntu@${aws_instance.atp.public_ip}"
}
