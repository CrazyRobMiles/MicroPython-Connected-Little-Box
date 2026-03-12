[← Back to README](../../README.md)

# UART Manager

Provides serial communication via UART for external device connectivity.

## Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `enabled` | bool | false | Enable/disable UART |
| `channel` | int | 0 | UART channel (0 or 1 on Pico) |
| `baud` | int | 9600 | Baud rate |
| `bits` | int | 8 | Data bits (typically 8) |
| `parity` | string | "None" | Parity: "None", "Even", or "Odd" |
| `stop` | int | 1 | Stop bits (1 or 2) |

## Services (Commands)

| Service | Description |
|---------|-------------|
| `hello` | Send test message "Hello from CLB" |
| `init` | Initialize/reinitialize UART with current settings |

## Events

This manager does not emit any events.

## Dependencies

This manager has no dependencies.

## States

- `ok` - UART initialized and ready
- `idle` - UART is idle
- `disabled` - UART is disabled
- `error` - Initialization error

## Example Settings

```json
{
    "uart": {
        "enabled": true,
        "channel": 0,
        "baud": 9600,
        "bits": 8,
        "parity": "None",
        "stop": 1
    }
}
```

## Console Usage

```
uart.hello
uart.init
```

## Code Usage

```python
# Get the UART manager instance
uart = clb.get_service_handle("uart")

# Send hello message
uart.hello()

# Reinitialize UART
uart.init()

# Write data directly
uart.uart.write(b'Hello from CLB\r\n')
uart.hello
uart.init
```

## Common Baud Rates

- 9600 - Standard
- 19200 - Fast
- 38400 - Faster
- 115200 - Fastest

## Notes

- UART provides serial communication with external devices
- On Pico, UART0 uses GPIO0/1, UART1 uses GPIO8/9
- The manager sends a "Hello from uart mamanger setup" message on initialization
- Parity options: "None" (no parity), "Even" (even parity), "Odd" (odd parity)

---

[↑ Back to README](../../README.md)
