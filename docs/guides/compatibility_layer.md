# CLB Compatibility Layer Documentation

This document explains how the Connected Little Box (CLB) compatibility
layer works to support both Raspberry Pi Pico (RP2040) and ESP32
platforms without code modifications.

## Overview

The compatibility layer (`compat.py`) is a small module that normalizes
differences between platforms, providing a unified interface for
managers. It detects the underlying platform automatically using
`sys.platform` and exposes flags like `IS_RP2` and `IS_ESP32`.

## Platform Detection

MicroPython returns: - `"rp2"` for Raspberry Pi Pico devices. -
`"esp32"` for ESP32 variants.

These flags guide platform-specific behaviors in the compatibility
layer.

## Pin Safety Handling

Different boards have different reserved or risky GPIO pins. The
compatibility layer includes `make_output_pin()` to validate pin numbers
and avoid forbidden or boot-critical pins.

### ESP32 Pin Gotchas

-   GPIO 6--11: Reserved for flash connections. Must not be used.
-   GPIO 0, 2, 15: Bootstrapping pins; avoid driving these low on
    startup.
-   Onboard LED is usually on **GPIO 2**.

### Pico Pin Gotchas

-   Onboard LED is on **GPIO 25**.

`make_output_pin` warns developers early before hardware faults occur.

## Timer Abstraction

ESP32 and RP2040 differ significantly in how they handle timers. RP2040
supports virtual timers with `Timer(-1)`, while ESP32 does not.

The compatibility layer provides: -
`start_periodic_timer(callback, tick_us)` - `cancel_timer(timer)`

### Timer Behavior Differences

-   ESP32 timers must be assigned IDs 0--3.
-   Sub-millisecond timers are unstable on ESP32 (can cause WDT resets).
-   Callback signatures differ across devices.

The compatibility layer wraps callbacks to ensure they receive no
arguments, maintaining consistent ISR behavior across devices.

## Timekeeping Helpers

The compatibility layer includes: - `monotonic_ms()` - `monotonic_us()`

These functions hide platform-specific differences in timekeeping
capabilities.

