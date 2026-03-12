[← Back to README](../../README.md)

# HullOS Manager

Manages the HullOS task scheduler for cooperative multitasking support.

## Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `enabled` | bool | false | Enable/disable HullOS task scheduling |

## Services (Commands)

This manager provides task scheduling and management services.

## Events

This manager does not emit any events.

## Dependencies

This manager has no dependencies.

## States

- `ok` - HullOS scheduler ready
- `disabled` - HullOS is disabled

## Example Settings

```json
{
    "hullos": {
        "enabled": false
    }
}
```

## Notes

- HullOS provides task scheduling for the CLB framework
- Tasks run in a cooperative multitasking environment
- Each manager's `update()` must yield control quickly to avoid starving other tasks

---

[↑ Back to README](../../README.md)
