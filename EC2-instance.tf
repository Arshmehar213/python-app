provider "aws" {
    region = "ap-south-1"
}        

data "aws_security_group" "existing-sg"{
    name = "web-Security-group"
}

resource "aws_instance" "web-instance"{
    ami = "ami-0356bc2cabc0dea3a"
    instance_type = "t2.micro"

    subnet_id = "subnet-09a2db23e24c995b4"
    vpc_security_group_ids = [data.aws_security_group.existing-sg.id]

    #associate_public_ip_address = true

    user_data = <<-EOF
                #!/bin/bash
                sudo apt update -y
                sudo apt install nginx -y
                sudo systemctl start nginx
                sudo systemctl enable nginx
                EOF
}