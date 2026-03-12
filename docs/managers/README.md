# Manager Reference Index

This directory contains documentation for all Connected Little Box (CLB) managers. Each manager handles a specific subsystem or hardware interface.

## Manager Categories

### Core Communication
- [WiFi Manager](wifi_manager.md) - Network connectivity
- [MQTT Manager](mqtt_manager.md) - IoT messaging and file transfer
- [UART Manager](uart_manager.md) - Serial communication

### Device Control
- [Blink Manager](blink_manager.md) - GPIO blinking patterns
- [Stepper Manager](stepper_manager.md) - Motor control
- [Pixel Manager](pixel_manager.md) - LED strip control
- [GPIO Manager](gpio_manager.md) - General I/O pins

### Display & UI
- [Display Manager](display_manager.md) - LCD and e-ink displays
- [Rotary Encoder Manager](rotary_encoder_manager.md) - User input knobs
- [Lamp Manager](lamp_manager.md) - Lamp control

### System Management
- [Clock Manager](clock_manager.md) - Time synchronization
- [Updater Manager](updater_manager.md) - Firmware updates
- [HullOS Manager](hullos_manager.md) - Task scheduling

### Specialized
- [SX-70R Manager](sx70r_manager.md) - Camera control via BLE
- [WordSearch Manager](wordsearch_manager.md) - Puzzle functionality

## Manager Information Structure

Each manager documentation contains:

- **Settings** - Configuration parameters in `settings.json`
- **Services** - Console commands available to the user
- **Events** - Events that the manager emits (which other managers can subscribe to)
- **Dependencies** - Other managers this manager depends on
- **States** - Possible states the manager can be in
- **Example Settings** - Sample configuration
- **Example Usage** - Command examples
- **Notes** - Additional information and best practices

## Enabling and Disabling Managers

To enable a manager, add an entry to `settings.json` with `"enabled": true`:

```json
{
    "blink": {
        "enabled": true,
        "pin": "LED",
        "delay_seconds": 1.0
    }
}
```

To disable a manager, set `"enabled": false` or remove the entry entirely.

## Manager Dependencies

Some managers depend on others. For example:
- **MQTT Manager** requires WiFi
- **Clock Manager** requires WiFi
- **Updater Manager** requires MQTT

If a dependency is disabled, the dependent manager will automatically disable itself.

## Creating Custom Managers

For information on creating your own managers, see the [CLB Manager Development Guide](/docs/guides/CLB_Manager_Development_Guide.md).

## Settings File Location

All manager settings are stored in `/firmware/settings.json`. Manager configuration is loaded at startup based on entries in this file.
