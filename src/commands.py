def get_bootstrap_website_command(github_username, github_token, email, domain):
    bootstrap_website_command = f"""
    # Enable persistent github credentials
    git config --global credential.helper store
    # Setup git credentials
    echo "https://{github_username}:{github_token}@github.com" > ~/.git-credentials
    chmod 600 ~/.git-credentials
    # Clone website repo
    git clone https://github.com/hashtagbowl/Gridoon ~/Gridoon
    # Make nginx-certbot.env
    cp ~/Gridoon/nginx-certbot.example.env ~/Gridoon/nginx-certbot.env
    sed -i "s/your@email.org/{email}/g" ~/Gridoon/nginx-certbot.env
    # Add domain name to nginx.conf
    sed -i "s/gridoon.com/{domain}/g" ~/Gridoon/user_conf.d/nginx.conf
    sed -i "s/www.gridoon.com/www.{domain}/g" ~/Gridoon/user_conf.d/nginx.conf
    # Build and up the container
    docker compose -f ~/Gridoon/docker-compose.yml -p gridoon-website up -d
    """
    return bootstrap_website_command

def get_cloud_init(server_username, server_password, root_password, user_public_key,):
    cloud_init = f"""
#cloud-config
timezone: "America/Winnipeg"
package_update: true
package_upgrade: true
packages:
- ca-certificates
- curl
- git
- ufw
- unattended-upgrades
users:
    - name: {server_username}
      ssh-authorized-keys:
          - {user_public_key}
      passwd: {server_password}
      primary_group: {server_username}
      groups: users, sudo
      shell: /bin/bash
      sudo: ['ALL=(ALL) NOPASSWD:ALL']
write_files:
    - path: /etc/apt/apt.conf.d/50unattended-upgrades
      permissions: '0644'
      content: |
          Unattended-Upgrade::Origins-Pattern {{
              "origin=Debian,codename=${{distro_codename}},label=Debian-Security";
              "o=Ubuntu,a=${{distro_codename}}-security";
          }};
          Unattended-Upgrade::Automatic-Reboot "true";
    - path: /etc/apt/apt.conf.d/10periodic
      permissions: '0644'
      content: |
          APT::Periodic::Update-Package-Lists "1";
          APT::Periodic::Download-Upgradeable-Packages "1";
          APT::Periodic::AutocleanInterval "7";
          APT::Periodic::Unattended-Upgrade "1";
runcmd:
    # Install Docker
    - echo "Starting runcmd execution" >> /var/log/cloud-init-debug.log
    - install -m 0755 -d /etc/apt/keyrings >> /var/log/cloud-init-debug.log 2>&1
    - curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc >> /var/log/cloud-init-debug.log 2>&1
    - chmod a+r /etc/apt/keyrings/docker.asc >> /var/log/cloud-init-debug.log 2>&1
    - |
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
        https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | \
        tee /etc/apt/sources.list.d/docker.list >> /var/log/cloud-init-debug.log 2>&1
    - apt-get update >> /var/log/cloud-init-debug.log 2>&1
    - apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin >> /var/log/cloud-init-debug.log 2>&1
    - echo "Docker installation complete" >> /var/log/cloud-init-debug.log
    # Enable unattended upgrades
    - systemctl enable --now unattended-upgrades >> /var/log/cloud-init-debug.log 2>&1
    # Open ports
    - ufw allow 80 >> /var/log/cloud-init-debug.log 2>&1
    - ufw allow 443 >> /var/log/cloud-init-debug.log 2>&1
    - ufw allow 22 >> /var/log/cloud-init-debug.log 2>&1
    # Enable UFW
    - echo "y" | ufw enable >> /var/log/cloud-init-debug.log 2>&1
    - ufw reload >> /var/log/cloud-init-debug.log 2>&1
    # Enable SSH password authentication and root login
    # sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/g' /etc/ssh/sshd_config >> /var/log/cloud-init-debug.log 2>&1
    - sed -i 's/#PermitRootLogin yes/PermitRootLogin yes/g' /etc/ssh/sshd_config >> /var/log/cloud-init-debug.log 2>&1
    # Restart SSH service
    - systemctl restart sshd >> /var/log/cloud-init-debug.log 2>&1
    # Set root password
    - echo "root:{root_password}" | chpasswd >> /var/log/cloud-init-debug.log 2>&1
    # Add SERVER_USER to docker group
    - adduser {server_username} docker
    """
    return cloud_init

rebuild_container_command = f"""
cd /root/Gridoon
git -C ~/Gridoon pull
docker compose down --volumes --remove-orphans
docker rm -f gridoon-nginx-certbot gridoon-nodejs
docker image prune -f
docker image rm -f gridoon-website-nodejs jonasal/nginx-certbot
docker volume rm -f gridoon-website_gridoon_data gridoon-website_nginx_secrets
docker compose up -d --no-deps --build nodejs
docker compose -f ~/Gridoon/docker-compose.yml -p gridoon-website up -d
"""

wait_for_cloud_init = "cloud-init status --wait"