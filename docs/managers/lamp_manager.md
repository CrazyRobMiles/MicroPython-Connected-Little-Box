[← Back to README](../../README.md)

# Lamp Manager

Controls lamp functionality (currently a placeholder/template manager).

## Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `enabled` | bool | false | Enable/disable lamp control |

## Services (Commands)

This manager currently provides no console commands.

## Events

This manager does not emit any events.

## Dependencies

This manager has no dependencies.

## States

- `ok` - Manager ready
- `disabled` - Lamp manager is disabled

## Example Settings

```json
{
    "lamp": {
        "enabled": false
    }
}
```

## Notes

- This manager is provided as a template for lamp control applications
- Implementation specific to your lamp hardware and control requirements
- Can be extended with GPIO, MQTT, or other control mechanisms

---

[↑ Back to README](../../README.md)
