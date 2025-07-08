Old style 
```
main.plugins.auto_backup.enabled = true
main.plugins.auto_backup.interval = "60"
main.plugins.auto_backup.max_tries = 3
main.plugins.auto_backup.backup_location = "/home/pi/"
main.plugins.auto_backup.files = [
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
 "/home/pi/.wpa_sec_uploads",
]
main.plugins.auto_backup.exclude = [
 "/etc/pwnagotchi/logs/*",
 "*.bak",
 "*.tmp",
]

```
New style
```
[main.plugins.auto_backup]
enabled = true
interval = "60"
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
exclude = [
  "/etc/pwnagotchi/logs/*"
]
# NO commands line is needed here either.
```


To restore after flashing 
```
sudo tar xzf /home/pi/NAME-backup.tar.gz -C /
```


