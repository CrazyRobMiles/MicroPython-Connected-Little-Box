# Connected Little Box
A tiny MicroPython operating system from Hull

If you've ever wanted the lights on your robot to flash while it moves around, this system is for you. If you want to make messages appear on a display alongside a ticking clock on top of an animated display, this system is for you. If you want to remotely command a device, or use one device to control another, or make a pair of servo-driven googly eyes track a face — this system is for you. It greatly simplifies the creation of connected devices that must run multiple simultaneous behaviours.

You can use the supplied managers to control WiFi, MQTT, clock, pixels, stepper and servo motors, audio playback, buttons, tilt sensors, and more. You can also create your own managers which provide services and generate events. The whole system is underpinned by an extensible JSON-based settings mechanism. There is also a serial interface for developing and testing which lets you issue commands to managers and view system status.

The system runs on Raspberry Pi Pico and ESP32 devices. A compatibility layer abstracts the timer functions used by stepper motors.

* [Roadmap](/docs/ROADMAP.md)
* [Status](/docs/STATUS.md)

## Documentation

### Getting Started & Guides
* [Getting Started](/docs/guides/Getting%20Started.md)
* [Application Definition](/docs/guides/App_Definition.md) - Creating and selecting device applications with `apps` and `select-app`
* [Settings Management](/docs/guides/Settings%20Management.md)
* [CLB Manager Development Guide](/docs/guides/CLB_Manager_Development_Guide.md)
* [CLB Messaging Guide](/docs/guides/CLB_Messaging_Guide.md)
* [CLB Compatibility Layer](/docs/guides/compatibility_layer.md)

### Manager Documentation

#### Core Communication
* [WiFi Manager](/docs/managers/wifi_manager.md) - Network connectivity
* [MQTT Manager](/docs/managers/mqtt_manager.md) - IoT messaging and file transfer
* [UART Manager](/docs/managers/uart_manager.md) - Serial communication

#### Device Control
* [Blink Manager](/docs/managers/blink_manager.md) - Control GPIO pins with blinking patterns
* [GPIO Manager](/docs/managers/gpio_manager.md) - General-purpose I/O control
* [Stepper Manager](/docs/managers/stepper_manager.md) - Stepper motor control and movement
* [Pixel Manager](/docs/managers/pixel_manager.md) - NeoPixel LED strip control

#### Servo & Animatronics
* [PCA9685 Manager](/docs/managers/pca9685_manager.md) - 16-channel I2C PWM/servo controller with orchestration
* [Eye Manager](/docs/managers/eye_manager.md) - Servo-driven googly eyes with look, blink, pose, and idle animation

#### Sensors & Input
* [Rotary Encoder Manager](/docs/managers/rotary_encoder_manager.md) - User input via rotary encoders
* [Tap Manager](/docs/managers/tap_manager.md) - Button tap detection (single, double, triple, long-press)
* [Tilt Manager](/docs/managers/tilt_manager.md) - Tilt-sensor gesture detection (tip, pulse, sequence)

#### Audio
* [DFPlayer Manager](/docs/managers/dfplayer_manager.md) - DFPlayer Mini MP3 audio playback over UART

#### Display & UI
* [Display Manager](/docs/managers/display_manager.md) - LCD and e-ink display support
* [Lamp Manager](/docs/managers/lamp_manager.md) - Lamp control template

#### System
* [Clock Manager](/docs/managers/clock_manager.md) - Time synchronisation and events
* [Updater Manager](/docs/managers/updater_manager.md) - Firmware update management
* [HullOS Manager](/docs/managers/hullos_manager.md) - Task scheduling

#### Specialised Apps
* [SX-70R Manager](/docs/managers/sx70r_manager.md) - Polaroid SX-70R camera control via BLE
* [WordSearch Manager](/docs/managers/wordsearch_manager.md) - Word search clock and puzzle display

Have Fun!

[Rob Miles](https://www.robmiles.com/)