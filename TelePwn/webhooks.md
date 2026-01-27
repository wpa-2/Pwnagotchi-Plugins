# 📚 TelePwn Webhooks Help Guide

Welcome to the quick and easy guide to setting up and using webhooks with TelePwn!

---

## 🌐 Understanding `url` vs `none`

When you create a webhook:

- If you are sending **data to the internet**, like Discord or an API → **Use a real URL** (`http://...` or `https://...`)
- If you are **running a command on your Pwnagotchi locally** → **Set URL to `none`**

| Scenario | URL Value | Example |
|:---------|:----------|:--------|
| Send alert to Discord | Actual webhook URL | `https://discord.com/api/webhooks/1234/abcd` |
| Rotate screen or reboot | `none` | Local command like `sudo reboot` |

✅ **Summary**:  
- If the action happens **on your Pwnagotchi**, set URL to **`none`**.  
- If the action sends something **out to the internet**, use the real **URL**.

---

## 📖 Basic Webhook Command Format

You create a webhook using:

```bash
/setwebhook <action> <url> [type] [request/command]
```

- **action**: The short name you will later trigger.
- **url**: A real URL (for `http`) or `none` (for `shell` and `plugin_toggle`).
- **type**: One of: `notify`, `shell`, `http`, `plugin_toggle`.
- **request/command**: The command to run or the HTTP request body.

---

## ✨ Useful Example Webhooks

Here are some extra examples for inspiration:

---

### 🔔 Simple Notification (Send a Telegram message)

```bash
/setwebhook ping none notify
```
Later trigger it with:
```bash
/webhook ping
```
✅ _Just sends a basic confirmation message back to you in Telegram._

---

### 🌍 HTTP POST to a Web API (e.g., IFTTT, Zapier)

```bash
/setwebhook webhook_test https://maker.ifttt.com/trigger/my_event/with/key/abcd1234 http POST {"value1":"Test Message"}
```
Later trigger it with:
```bash
/webhook webhook_test
```
✅ _Sends data out to IFTTT, Zapier, or a custom API._

---

### 🖥️ Local Shell Command (Restart WiFi)

```bash
/setwebhook restart_wifi none shell sudo systemctl restart networking
```
Later trigger it with:
```bash
/webhook restart_wifi
```
✅ _Restarts the network stack locally without rebooting everything._

---

### 🛠️ Local Shell Command with Variable Placeholder

Rotate the Pwnagotchi screen easily by passing degrees!

```bash
/setwebhook rotate_screen none shell sudo sed -i '/ui\.display\.rotation/c\ui.display.rotation = {degrees}' /etc/pwnagotchi/config.toml && sudo killall -USR1 pwnagotchi
```
Then you can rotate on the fly like:

```bash
/webhook rotate_screen degrees=90
```
or

```bash
/webhook rotate_screen degrees=180
```
✅ _Edits `config.toml` and reloads without needing a full system reboot._

---

### ⚙️ Toggle a Plugin (Example: Enable or Disable `memtemp`)

```bash
/setwebhook toggle_memtemp none plugin_toggle
```
Later toggle it with:

```bash
/webhook toggle_memtemp memtemp
```
✅ _Turns the `memtemp` plugin on/off dynamically._

---

## ⚡ Quick Troubleshooting

- **Webhook not working?**
  - Check the webhook list `/etc/pwnagotchi/telepwn_webhooks.toml`
  - Check logs:  
    ```bash
    sudo grep webhook /etc/pwnagotchi/log/pwnagotchi.log
    ```

- **Placeholder not replaced?**
  - Double check you passed the correct `key=value` after `/webhook`.

- **HTTP URL failing?**
  - Try the URL manually with `curl` first to debug it.

---

🚀 **Now you can automate your Pwnagotchi like a pro with TelePwn Webhooks!**
