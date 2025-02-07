import base64
import hashlib
import os
from pathlib import Path
import time
import traceback

from dotenv import find_dotenv, load_dotenv, set_key, unset_key
import paramiko

from commands import get_bootstrap_website_command, rebuild_container_command, get_cloud_init, wait_for_cloud_init
from do_api import DigitalOceanManager

dotenv_path = find_dotenv()
load_dotenv(dotenv_path)

# Setup env vars
DO_TOKEN = os.environ.get("DO_TOKEN")
EMAIL = os.environ.get("EMAIL")
DOMAIN = os.environ.get("DOMAIN")
GITHUB_USERNAME = os.environ.get("GITHUB_USERNAME")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
SERVER_USERNAME = os.environ.get("SERVER_USERNAME")
SERVER_PASSWORD = os.environ.get("SERVER_PASSWORD")
ROOT_PASSWORD = os.environ.get("ROOT_PASSWORD")
IP_ADDRESS = os.environ.get("IP_ADDRESS")
ROOT_KEY_NAME = "gridoon_root"
USER_KEY_NAME = "gridoon_user"

# Digial Ocean client init
do_client = DigitalOceanManager(token=DO_TOKEN)

# Paramiko client init
ssh_client = paramiko.client.SSHClient()
ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

containers = [
    {
        "name": "gridoon-nodejs",
        "ready_status": "exited"
    },
    {
        "name": "gridoon-nginx-certbot",
        "ready_status": "running"
    }
]

def connect_with_retry(hostname, username, private_key_path, port=22, retries=10, delay=7):
    """
    Tries to connect to an SSH server with retries.
    
    :param hostname: The hostname or IP address of the server.
    :param username: The username for SSH.
    :param private_key_path: Path to the private key file.
    :param port: SSH port (default is 22).
    :param retries: Number of retries before giving up.
    :param delay: Delay (in seconds) between retries.
    :return: A connected SSH client instance, or None if all retries fail.
    """
    private_key = paramiko.RSAKey.from_private_key_file(private_key_path)
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    for attempt in range(1, retries + 1):
        try:
            print(f"Attempt {attempt} of {retries} to connect to {hostname}...")
            ssh_client.connect(hostname=hostname, port=port, username=username, pkey=private_key)
            print("Connected successfully!")
            return ssh_client  # Return the connected client
        except (paramiko.ssh_exception.NoValidConnectionsError, paramiko.ssh_exception.SSHException) as e:
            print(f"Connection failed: {e}. Retrying in {delay} seconds...")
            time.sleep(delay)
    
    print("All retry attempts failed. Unable to connect.")
    return None

def get_droplet_ip():
    global IP_ADDRESS
    unset_key(dotenv_path, "IP_ADDRESS")

    droplet = do_client.get_droplet(name="gridoon")

    for ip in droplet["networks"]["v4"]:
        if ip["type"] == "public":
            set_key(dotenv_path, "IP_ADDRESS", ip["ip_address"])
            load_dotenv(dotenv_path, override=True)
            IP_ADDRESS = os.environ.get("IP_ADDRESS")
            print(f"Found server IP {IP_ADDRESS}")

def generate_keys(key_name):
    script_dir = Path(__file__).parent
    key_dir = script_dir / "keys"
    key_dir.mkdir(parents=True, exist_ok=True)

    # Set key file paths
    private_key_file = key_dir / f"{key_name}.pk"
    public_key_file = key_dir / f"{key_name}.pubk"

    # Generate 4096 bit RSA key
    private_key = paramiko.RSAKey.generate(bits=4096)
    public_key = f"{private_key.get_name()} {private_key.get_base64()}"

    # Write keys to disk
    private_key.write_private_key_file(private_key_file)
    with open(public_key_file, "w") as pub_file:
        pub_file.write(public_key)

def get_local_keys(key_name):
    script_dir = Path(__file__).parent
    key_dir = script_dir / "keys"

    private_key_path = key_dir / f"{key_name}.pk"
    public_key_path = key_dir / f"{key_name}.pubk"

    private_key = None
    public_key = None
    
    if private_key_path.exists() == False and public_key_path.exists() == False:
        # If there is no public key and no private key, make new ones
        generate_keys(key_name)

    elif private_key_path.exists() == False ^ public_key_path.exists() == False:
        # If there is (somehow) only have one key, delete it and make new private and public keys
        if private_key_path.exists():
            file_path.unlink()

        elif public_key_path.exists():
            file_path.unlink()

        generate_keys(key_name)

    # Assuming private key and public key exist now
    private_key = private_key_path

    with open(public_key_path, "r") as pk:
        public_key = pk.readlines()[0]

    return public_key, private_key

def verify_keys(key_name):
    private_key = None
    public_key = None

    try:
        do_key = do_client.get_key(name=key_name)

        if not do_key:
            # If no DigitalOcean key with the given name was found
            # Get local ssh keys and upload them
            public_key, private_key = get_local_keys(key_name)
            do_key = do_client.upload_key(public_key, key_name)

        elif do_key:
            # If the DigitalOcean key with the given name was found
            public_key, private_key = get_local_keys(key_name)

            if do_key["public_key"] != public_key:
                # If DigitalOcean public key doesn't match local public key
                # Delete the DigitalOcean key and upload the local public key
                do_client.delete_key(do_key["id"])
                do_key = do_client.upload_key(public_key, key_name)

        return do_key, private_key, public_key

    except Exception as e:
        print("SSH key verification failed, script is doomed", e)
        traceback.print_exc()

def wait_for_docker(ssh_client, container_name, status, timeout=600):
    start_time = time.time()
    while time.time() - start_time < timeout:
        stdin, stdout, stderr = ssh_client.exec_command(f"docker inspect --format='{{{{.State.Status}}}}' {container_name}")
        output = stdout.read().decode().strip()
        print(output)
        if output == status:
            print(f"{container_name} is ready or finished running.")
            return True
        time.sleep(5)

def send_server_command(commands, ip_address, username, private_key, docker_status=False, containers=None):
    ssh_client = connect_with_retry(hostname=ip_address, port=22, username=username, private_key_path=private_key)
    
    # Send website setup commands
    stdin, stdout, stderr = ssh_client.exec_command(commands)
    stdout.channel.recv_exit_status()  # Wait for command to finish
    output = stdout.read().decode()
    print(output)

    # Check docker status
    if docker_status == True:
        for container in containers:
            wait_for_docker(ssh_client, container["name"], container["ready_status"])

    # Close connection to server
    ssh_client.close()

def main():
    # Look for a Droplet named gridoon
    gridoon_droplet = do_client.get_droplet(name="gridoon")
    new_droplet = None
    droplet_id = None
    if gridoon_droplet:
        droplet_id = gridoon_droplet["id"]
    
    # Verify user and root SSH keys
    do_root_key, root_private_key, root_public_key = verify_keys(ROOT_KEY_NAME)
    do_user_key, user_private_key, user_public_key = verify_keys(USER_KEY_NAME)

    if not gridoon_droplet: # If Droplet named "gridoon" does not exist
        # Put env vars in cloud_init config
        cloud_init = get_cloud_init(SERVER_USERNAME, SERVER_PASSWORD, ROOT_PASSWORD, user_public_key)

        # Make new Droplet
        new_droplet = do_client.make_droplet(
            name="gridoon",
            region="tor1",
            size="s-1vcpu-1gb",
            image="ubuntu-24-04-x64",
            root_key_id=do_root_key["id"],
            cloud_init=cloud_init
        )

        droplet_id = new_droplet["id"]
        get_droplet_ip()

        print(f"Now would be a good time to update your DNS with the new droplet IP: {IP_ADDRESS}")
        print("Connecting to server to see when the server finishes building")
        send_server_command(wait_for_cloud_init, IP_ADDRESS, "root", root_private_key)
        print("Server ready")

    print("Making the Droplet stronger so we can actually make the website")
    do_client.resize_with_power_cycle(droplet_id, "s-2vcpu-2gb")

    print("Making website")
    if gridoon_droplet:
        send_server_command(rebuild_container_command, IP_ADDRESS, SERVER_USERNAME, user_private_key, docker_status=True, containers=containers)
    if new_droplet:
        commands = get_bootstrap_website_command(GITHUB_USERNAME, GITHUB_TOKEN, EMAIL, DOMAIN)
        send_server_command(commands, IP_ADDRESS, SERVER_USERNAME, user_private_key, docker_status=True, containers=containers)

    print("Making the Droplet weaker so we don't give digital ocean too much money")
    do_client.resize_with_power_cycle(droplet_id, "s-1vcpu-1gb")
    print("Website should come up shortly! Please give it at least 5 minutes before running the script again.")
    print("If the website does not come up, make sure you have created the proper DNS records, then run the script again")

if __name__ == "__main__":
    main()