[← Back to README](../../README.md)

# WordSearch Manager

Provides word search puzzle functionality.

## Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `enabled` | bool | false | Enable/disable word search |

## Services (Commands)

This manager provides word search puzzle generation and solving services.

## Events

This manager does not emit any events.

## Dependencies

This manager has no dependencies.

## States

- `ok` - Manager ready
- `disabled` - Word search is disabled

## Example Settings

```json
{
    "wordsearch": {
        "enabled": false
    }
}
```

## Notes

- This manager provides word search puzzle functionality
- Can be used for entertainment or puzzle applications
- Integrates with display managers for output

---

[↑ Back to README](../../README.md)
