import time

from pydo import Client


class DigitalOceanManager:
    def __init__(self, token):
        self.client = Client(token=token)

    def handle_action_response(self, response):
        """
        Handle DigitalOcean API call responses for droplet actions.

        :param response: The API response as a dictionary.
        :return: The action ID if successful, or raised exception if unsuccessful.
        """
        if "action" in response:
            action_id = response["action"]["id"]
            print(f"Action successful: {response["action"]["type"]}, {response["action"]["status"]}")
            return action_id
        
        if "id" in response:
            error_message = response["message"]
            print(f"Error: {error_message}")
            raise RuntimeError(f"DigitalOcean API Action error: {error_message}")

        raise ValueError("Unexpected response format from DigitalOcean API.")

    def handle_ssh_key_response(self, response):
        """
        Handle DigitalOcean API call responses for SSH Key creation.

        :param response: The API response as a dictionary.
        :return: The SSH Key if successful, or raised exception if unsuccessful.
        """
        if "ssh_key" in response:
            ssh_key = response["ssh_key"]
            print(f"SSH Key {ssh_key["name"]} successfully uploaded to DigitalOcean")
            return ssh_key
        
        if "id" in response:
            error_message = response["message"]
            print(f"Error: {error_message}")
            raise RuntimeError(f"DigitalOcean API SSH Key creation error: {error_message}")

    def wait_for_action(self, action_id, timeout=300, interval=5):
        """
        Wait for a DigitalOcean action to complete.

        :param action_id: The ID of the action being waited for.
        :param timeout: The maximum wait time in seconds.
        :param interval: The time in seconds between status checks.
        :return: True if the action completes successfully, and False if otherwise.
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                response = self.call_api(
                    self.client.actions.get,
                    action_id=action_id
                )
                status = response["action"]["status"]

                if status == "completed":
                    print(f"Action {action_id} completed successfully.")
                    return True
                elif status == "errored":
                    print(f"Action {action_id} failed.")
                    return False

                time.sleep(interval)
            except Exception as e:
                print(f"Error while monitoring action {action_id}, {e}")
                return False

    def wait_for_droplet(self, id, timeout=300, interval=5):
        """
        Wait for a new Droplet to become Active.

        :param id: The ID of the Droplet we're waiting for.
        :param timeout: The maximum wait time in seconds.
        :param interval: The time in seconds between status checks.
        :return:
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                response = self.call_api(
                    self.client.droplets.get,
                    droplet_id=id
                )
                status = response["droplet"]["status"]

                if status == "active":
                    print(f"Droplet {id} creation complete.")
                    return True

                time.sleep(interval)
            except Exception as e:
                print(f"Error while monitoring Droplet {id} creation, {e}")
                return False
        
    def call_api(self, api_method, *args, **kwargs):
        """
        A generic wrapper for calling DigitalOcean API methods.

        :param api_method: The method to call (from pydo.Client).
        :param args: Positional arguments for the API method.
        :param kwargs: Keyword arguments for the API method.
        :return: The API response if successful.
        :raises RuntimeError: If the API call returns an error.
        """
        try:
            response = api_method(*args, **kwargs)
            return response
        except RuntimeError as e:
            print(f"DigitalOcean API runtime error: {e}")
            raise
        except Exception as e:
            print(f"An unexpected error occurred while Calling DigitalOcean API: {e}")
            raise

    def power_droplet(self, droplet_id, type):
        """
        Tries to turn on or power off a droplet.
        
        :param droplet_id: The ID of the droplet to be powered on.
        :param type: The type of action being performed (power_on, shutdown).
        :return: The action ID of the power operation, or a response indicating the action failed.
        """
        response = self.call_api(
            self.client.droplet_actions.post,
            droplet_id=droplet_id,
            body={"type": type}
        )

        action_id = self.handle_action_response(response)
        self.wait_for_action(action_id)

        return action_id

    def resize_droplet(self, droplet_id, size):
        """
        Resize a droplet to a new size.

        :param droplet_id: The ID of the droplet being resized.
        :param size: The new size (e.g. "s-2vcpu-2gb).
        :return: The action ID of the resize operation, or a response indicating the action failed.
        """
        response = self.call_api(
            self.client.droplet_actions.post,
            droplet_id=droplet_id,
            body={"type": "resize", "size": size}
        )
        action_id = self.handle_action_response(response)
        self.wait_for_action(action_id)

        return action_id

    def resize_with_power_cycle(self, droplet_id, size):
        """
        Resizes a droplet safely by powering it off, resizing, and powering it back on.

        :param droplet_id: The ID of the droplet to resize.
        :param size: The new size of the droplet (e.g. "s-2vcpu-2gb").
        :return: True if the resize is successful, False otherwise.
        """
        try:
            print(f"Powering off the droplet {droplet_id}...")
            shutdown_action_id = self.power_droplet(droplet_id, type="shutdown")

            print(f"Resizing the droplet {droplet_id} to size {size}...")
            resize_action_id = self.resize_droplet(droplet_id, size)

            print(f"Powering on the droplet {droplet_id}...")
            power_on_action_id = self.power_droplet(droplet_id, type="power_on")

            print(f"Droplet {droplet_id} resized to {size} and powered on successfully.")
            return True
        
        except Exception as e:
            print(f"An error occurred while resizing the droplet {droplet_id}: {e}")
            return False

    def get_droplet(self, droplet_id=None, name=None):
        """
        Get a Droplet associated with the DigitalOcean account by ID or name.

        :param name: Optional, the Droplet name to get.
        :param droplet_id: Optional, the Droplet ID to get.
        :return: The specified Droplet as a dictionary.
        """

        if droplet_id:
            response = self.call_api(
                self.client.droplets.get,
                droplet_id=droplet_id
            )
            if "droplet" in response:
                droplet = response["droplet"]
                print(f"Droplet {droplet["name"]} successfully fetched from DigitalOcean")
                return droplet

            if "id" in response:
                error_message = response["message"]
                print(f"Error: {error_message}")
                raise RuntimeError(f"DigitalOcean API Droplet fetch error: {error_message}")

        elif name:
            response = self.call_api(
                self.client.droplets.list
            )
            if "droplets" in response:
                droplets = response["droplets"]
                droplet = [droplet for droplet in droplets if droplet["name"] == name]

                if len(droplet) < 1:
                    print(f"Droplet {name} could not be found")
                    return False

                droplet = droplet[0]
                print(f"Droplet {droplet["name"]} successfully fetched from DigitalOcean")
                return droplet
            
            if "id" in response:
                error_message = response["message"]
                print(f"Error: {error_message}")
                raise RuntimeError(f"DigitalOcean API Droplets fetch error: {error_message}")

        else:
            raise Exception(f"'name' or 'key_id' must be specified when calling DigitalOceanManager.get_droplet")

    def get_droplets(self):
        """
        Get all Droplets associated with the DigitalOcean account.
        
        :return: A list of Droplets as dictionaries.
        """
        response = self.call_api(
            self.client.droplets.list
        )
        if "droplets" in response:
            droplets = response["droplets"]
            print(f"{len(droplets)} successfully fetched from DigitalOcean")
            return droplets

        if "id" in response:
            error_message = response["message"]
            print(f"Error: {error_message}")
            raise RuntimeError(f"DigitalOcean API Droplets fetch error: {error_message}")

    def make_droplet(self, name, region, size, image, root_key_id, cloud_init):
        """
        Make a new Droplet with the DigitalOcean account.

        :param name: The name of the new Droplet.
        :param region: The keyword for the datacenter location to make the new Droplet in.
        :param size: The keyword for the VPS size of the new Droplet.
        :param image: The keyword for the OS Image to install on the new Droplet.
        :param root_key_id: The ID of the Digital Ocean SSH Key to use for the new Droplet's root user.
        :param cloud_init: The cloud-init config as a string.
        :return: The newly created Droplet as a dictionary.
        """
        response = self.call_api(
            self.client.droplets.create,
            body={"name": name, "region": region, "size": size, "image": image, "ssh_keys": [f"{root_key_id}"], "user_data": cloud_init}
        )
        if "droplet" in response:
            droplet = response["droplet"]
            print(f"Successfully created Droplet {droplet["name"]}")
            self.wait_for_droplet(droplet["id"])
            return droplet

        if "id" in response:
            error_message = response["message"]
            print(f"Error: {error_message}")
            raise RuntimeError(f"DigitalOcean API Droplets fetch error: {error_message}")


    def get_key(self, key_id=None, name=None):
        """
        Get an SSH Key associated with the DigitalOcean account.
        
        :param key_id: Optional, the SSH Key ID to get.
        :param name: Optional, the SSH Key name to get.
        :return: The specified SSH Key as a dictionary.
        """
        if key_id:
            response = self.call_api(
                self.client.ssh_keys.get,
                ssh_key_identifier=key_id
            )
            if "ssh_key" in response:
                ssh_key = response["ssh_key"]
                print(f"SSH Key {ssh_key["id"]} successfully fetched from DigitalOcean")
                return ssh_key
            
            if "id" in response:
                error_message = response["message"]
                print(f"Error: {error_message}")
                raise RuntimeError(f"DigitalOcean API SSH Key fetch error: {error_message}")

        elif name:
            response = self.call_api(
                self.client.ssh_keys.list
            )
            if "ssh_keys" in response:
                ssh_keys = response["ssh_keys"]
                ssh_key = [ssh_key for ssh_key in ssh_keys if ssh_key["name"] == name]

                if len(ssh_key) < 1:
                    print(f"SSH Key {name} could not be found")
                    return False

                ssh_key = ssh_key[0]
                print(f"SSH Key {ssh_key["name"]} successfully fetched from DigitalOcean")
                return ssh_key
            
            if "id" in response:
                error_message = response["message"]
                print(f"Error: {error_message}")
                raise RuntimeError(f"DigitalOcean API SSH Key fetch error: {error_message}")

        else:
            raise Exception(f"'name' or 'key_id' must be specified when calling DigitalOceanManager.get_key")

    def get_keys(self):
        """
        Get all SSH Keys associated with the DigitalOcean account.
        
        :return: List of SSH Keys as dictionaries.
        """
        response = self.call_api(
            self.client.ssh_keys.list
        )
        if "ssh_keys" in response:
            ssh_keys = response["ssh_keys"]
            print(f"{len(ssh_keys)} SSH Keys successfully fetched from DigitalOcean")
            return ssh_keys
        
        if "id" in response:
            error_message = response["message"]
            print(f"Error: {error_message}")
            raise RuntimeError(f"DigitalOcean API SSH Key fetch error: {error_message}")

    def upload_key(self, public_key, key_name):
        """
        Upload a public key for use with droplet SSH authentication.

        :param public_key: The public key to be used for authentication.
        :param key_name: The name of the public key.
        :return: The SSH Key JSON object as a dictionary.
        """
        response = self.call_api(
            self.client.ssh_keys.create,
            body={"public_key": public_key, "name": key_name}
        )

        if "ssh_key" in response:
            ssh_key = response["ssh_key"]
            print(f"SSH Key {ssh_key["name"]} successfully uploaded to DigitalOcean")
            return ssh_key
        
        if "id" in response:
            error_message = response["message"]
            print(f"Error: {error_message}")
            raise RuntimeError(f"DigitalOcean API SSH Key creation error: {error_message}")

    def delete_key(self, key_id):
        """
        Delete a public key from your DigitalOcean account.

        :param key_id: The DigitalOcean ID of the SSH Key to be deleted.
        :return: True if the key was deleted, False if not.
        """
        response = self.call_api(
            self.client.ssh_keys.delete,
            ssh_key_identifier=key_id
        )

        if not response:
            return True

        if "id" in response:
            error_message = response["message"]
            print(f"Error: {error_message}")
            raise RuntimeError(f"DigitalOcean API SSH Key deletion error: {error_message}")
        