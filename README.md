Rebuild the gridoon website from scratch, or update to the latest version. If you delete the gridoon Droplet on Digital Ocean, this will make a new Droplet and rebuild the website.

Directions:
- Install Python. You can get the latest version [here](https://www.python.org/downloads/)
- Copy the .env.example file and rename it to .env
- Open .env in notepad. Fill in the values after the equals sign.
- - IP_ADDRESS can be left blank.
- - SERVER_USERNAME is whatever you want as a username for the server. Just put gridoon if you're unsure.
- - DOMAIN must be "website.com" i.e. gridoon.com
- - For the ROOT_PASSWORD and SERVER_PASSWORD just come up with something unique. Use a different passwords for each one.
- - For GITHUB_TOKEN and DO_TOKEN (DigitalOcean Token) new ones will probably have to be generated. You can choose to make them never expire if you wish.
- If you deleted the old gridoon Droplet, login to your DNS provider and be ready to update the IP when the script tells you to.
- Double click manage_gridoon.bat
- There may be periods of 5 to 10 minutes where nothing appears to be happening. Be patient!
- ???
- Profit!