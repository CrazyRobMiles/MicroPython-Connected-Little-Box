# DFPlayer Manager

Controls a DFPlayer Mini MP3 module over a UART serial connection. Plays audio tracks stored on a MicroSD card by absolute track number. Used by the WordSearch clock app for alarm sounds.

The DFPlayer accesses files by the order they were copied to the card, not by filename. Track 1 is the first file written, track 2 the second, and so on.

## Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Enable this manager |
| `uart_id` | int | `1` | UART bus number |
| `tx_pin` | int | `5` | TX pin number |
| `rx_pin` | int | `4` | RX pin number |
| `volume` | int | `17` | Playback volume (0–30) |

## Services

| Command | Syntax | Description |
|---------|--------|-------------|
| `play` | `play <track_no>` | Play track by number (1-based, order files were written to card) |
| `stop` | `stop` | Stop current playback |
| `volume` | `volume <0..30>` | Set playback volume |

## Dependencies

None.

## States

| State | Description |
|-------|-------------|
| `idle` | Ready and waiting |
| `disabled` | Manager is disabled or failed to initialise |

## Notes

- On startup the manager resets the DFPlayer and selects the MicroSD card as the playback source.
- Volume is re-applied from settings each time `play` is called so that settings changes take effect without restarting.
- EQ is set to Bass mode on each play call.
- Track numbering depends entirely on the order files were written to the SD card, not alphabetical order. Copy `alarm_off` first, `alarm_on` second, then the remaining tracks.

## Example Settings

```json
{
    "dfplayer": {
        "enabled": true,
        "uart_id": 1,
        "tx_pin": 5,
        "rx_pin": 4,
        "volume": 20
    }
}
```

## Example Usage

```
dfplayer play 1        # play the first track (alarm off message)
dfplayer play 2        # play the second track (alarm on message)
dfplayer play 5        # play track 5
dfplayer volume 25     # increase volume
dfplayer stop          # stop playback
```
