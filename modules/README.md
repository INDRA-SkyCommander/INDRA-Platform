# Modules

These scripts are intended for **authorized** research, lab demos, and defensive testing **only**.  
Only run them on hardware and networks you own or have explicit permission to test.

## What’s in this folder

- **deauth.py** — Wireless test helper used in controlled environments. Reads target/interface options from `data/module_input_data.json`.
- **skyjack.py** — Drone interaction workflow used in controlled environments. Also reads configuration from `data/module_input_data.json`.

## Configuration

Both modules expect a JSON file at:

- `data/module_input_data.json`

At a minimum, it should include target metadata and options (example shape):

```json
{
  "target_name": "Example",
  "target_info": { "mac_address": "xx:xx:xx:xx:xx:xx", "channel": 1 },
  "options": { "interface": "wlan0", "packets": 30 }
}
```

## Safety notes

Wireless testing can disrupt nearby devices. Use a shielded environment or approved lab space, and follow your organization’s policies.
