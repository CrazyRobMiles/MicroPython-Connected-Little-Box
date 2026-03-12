## Version 1.0.2

- Added version to CLB core
- Added MQTT file receipt beta for testing
- Reworked setting input to handle structured setting values (for example stepper motor settings) and updated settings guide
- Added manager notification of setting changes
- Added updated Clock.json file for 16x16 led wordsearch
## Version 1.0.3

- Turned off low power mode in WiFi startup
- Modified the clock to use a non-blocking version of ntime
- Update manager now performs manifest download and local version check
- Added version values to all code file
- Added alpha display manager
- Added alpha uart manager

## Version 1.0.4

- manager loading is now controlled by settings.json, and not by parsing the managers folder
- added rotary encoder manager
- added SX-70R Bluetooth manager
- added a lamp manager for a rotary encoder controlled light
- added a prototype uart manager 
- added a GPIO manager 
- moved dependency configuration from manager source code into settings.json
- added manager documentation
- added reset.py program to reset a device
- added new packed clock wordsearch design