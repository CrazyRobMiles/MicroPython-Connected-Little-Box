# MicroPython-HullOS
A tiny operating system from Hull written in MicroPython

If you've ever wanted the lights on your robot to flash while it moves around; this system is for you. If you want to make messages appear on a display alongside a ticking clock on top of an animated display, this system is for you. If you want to remotely command a remote device, or use one device to control another, this system is for you. It greatly simplifies the creation of connected devices which must contain multiple simultaneous behaviours. 

You can use the supplied managers to control WiFi, MQTT, clock, pixel and stepper motors. However, you can also create your own managers which can provide services and generate events. The whole system is underpinned by an extensible JSON based setting storage mechanism which provides data obfuscation. There is also a serial interface you can use for developing and testing which lets you issue commands to managers and view the status of the system. 

The system can run on Raspberry Pi PICO and ESP32 devices. A compatibility layer is provided to abstract the timer functions used by the stepper motors. 

* [Getting Started](/docs/guides/Getting%20Started.md)
* [Settings Management](/docs/guides/Settings%20Management.md)
* [CLB Manager Development Guide](/docs/guides/CLB_Manager_Development_Guide.md)
* [CLB Messaging Guide](/docs/guides/CLB_Messaging_Guide.md)
* [CLB Compatibility Layer](/docs/guides/compatibility_layer.md)

Have Fun!

[Rob Miles](https://www.robmiles.com/)