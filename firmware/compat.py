version = "1.0.0"

# compat.py
#
# Cross-platform helpers so CLB managers can run on both:
#  - Raspberry Pi Pico / Pico W (rp2)
#  - ESP32 (esp32)
#
# Provides:
#   PLATFORM, IS_RP2, IS_ESP32
#   make_output_pin()
#   start_periodic_timer()
#   cancel_timer()
#   monotonic_us(), monotonic_ms()
#
# Managers should import this instead of using machine.Pin / machine.Timer directly.

import sys
import machine
import time

PLATFORM = sys.platform         # 'rp2', 'esp32', 'esp8266', etc.
IS_RP2 = PLATFORM == "rp2"
IS_ESP32 = PLATFORM == "esp32"

# ESP32 has internal flash wired to GPIO 6–11.
_ESP32_FORBIDDEN_PINS = set(range(6, 12))


# -------------------------------------------------------------
# PLATFORM IDENTIFICATION
# -------------------------------------------------------------

def platform_name():
    """Return a friendly name for logs and status messages."""
    if IS_RP2:
        return "rp2 (Raspberry Pi Pico)"
    if IS_ESP32:
        return "esp32"
    return PLATFORM or "unknown"


# -------------------------------------------------------------
# PIN CREATION
# -------------------------------------------------------------

def make_output_pin(gpio):
    """
    Cross-port safe creation of a machine.Pin output.

    Validates pins that cannot be used on ESP32 (6–11).
    Leaves Pico completely flexible.
    """
    if not isinstance(gpio, int):
        raise ValueError(f"GPIO must be an integer, got: {gpio!r}")

    if IS_ESP32:
        if gpio in _ESP32_FORBIDDEN_PINS:
            raise ValueError(
                f"GPIO {gpio} cannot be used on ESP32 (connected to flash). "
                "Change your configuration."
            )
    return machine.Pin(gpio, machine.Pin.OUT)


# -------------------------------------------------------------
# TIMER WRAPPER
# -------------------------------------------------------------
def start_periodic_timer(callback, tick_us=1000):
    """
    Start a periodic timer in a way that works on both ESP32 and RP2040.

    Handles:
      - ESP32 not supporting Timer(-1)
      - ESP32 requiring timers 0–3
      - Pico supporting Timer(-1)
      - Timer callback signatures varying
    """

    # ESP32 cannot safely run sub-ms ticks
    effective_tick_us = int(tick_us)
    if IS_ESP32 and effective_tick_us < 1000:
        effective_tick_us = 1000

    # ---- NORMALISE CALLBACK SIGNATURE ----
    def wrapped(*args, **kwargs):
        try:
            callback()
        except Exception as e:
            try:
                sys.print_exception(e)
            except:
                pass

    # ---- SELECT PLATFORM-SAFE TIMER INSTANCE ----
    if IS_ESP32:
        # Always choose Timer(0) on ESP32.
        # It is guaranteed to exist and safe for periodic ISR use.
        try:
            t = machine.Timer(0)
        except Exception as e:
            raise RuntimeError(f"ESP32 Timer(0) failed: {e}")
    else:
        # Pico / RP2 supports virtual timer (-1)
        try:
            t = machine.Timer(-1)
        except Exception:
            # Rarely needed, but a safe fallback
            t = machine.Timer(0)

    # ---- TRY HIGH-RES MODE FIRST (freq) ----
    try:
        freq = int(1_000_000 // effective_tick_us)
        if freq > 0:
            t.init(freq=freq, mode=machine.Timer.PERIODIC, callback=wrapped)
            return t
    except Exception:
        pass

    # ---- FALL BACK TO PERIOD (milliseconds) ----
    period_ms = max(1, effective_tick_us // 1000)
    t.init(period=period_ms, mode=machine.Timer.PERIODIC, callback=wrapped)
    return t

def cancel_timer(timer):
    """Safely deinitialize a timer if it exists."""
    try:
        if timer:
            timer.deinit()
    except Exception:
        pass


# -------------------------------------------------------------
# MONOTONIC TIME ACCESS
# -------------------------------------------------------------

def monotonic_us():
    return time.ticks_us()

def monotonic_ms():
    return time.ticks_ms()
