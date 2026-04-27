[← Back to README](../../README.md)

# HullOS Manager

Manages the HullOS task scheduler for cooperative multitasking support.

## Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `enabled` | bool | false | Enable/disable HullOS task scheduling |
| `default_program` | string | "default.pyish" | Filename of the program to run on power-up |
| `program_folder` | string | "/HullOS/code" | Folder on the device where `.pyish` programs are stored |
| `run on power up` | bool | true | Whether to automatically start `default_program` on boot |

## Services (Commands)

| Service | Description |
|---------|-------------|
| `start <name> <file>` | Start a named task by loading `<file>` from the program folder |

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
