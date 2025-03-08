```
[main.plugins.auto_backup]
enabled = false
interval = "daily"    # or "hourly", or a number (minutes)
max_tries = 0
backup_location = "/home/pi/"
files = [
  "/root/settings.yaml",
  "/root/client_secrets.json",
  "/root/.api-report.json",
  "/root/.ssh",
  "/root/.bashrc",
  "/root/.profile",
  "/home/pi/handshakes",
  "/root/peers",
  "/etc/pwnagotchi/",
  "/usr/local/share/pwnagotchi/custom-plugins",
  "/etc/ssh/",
  "/home/pi/.bashrc",
  "/home/pi/.profile",
  "/home/pi/.wpa_sec_uploads"
]
exclude = [ "/etc/pwnagotchi/logs/*"]
commands = [ "tar cf {backup_file} {files}"]

```


To restore after flashing 
```
sudo tar xf /home/pi/NAME-backup.tar -C /
```


