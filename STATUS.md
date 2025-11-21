# Component Status
## Connected Little Boxes
- Dynamic loading of managers: stable
- Setting storage and update: stable
- Console command processing: stable
- Manager feature integration: stable

## HullOS
- Parser: performs console commands
- Execution engine: will run command sequences. Can set default script to run at boot. 
- Expressions: not implemented
- Control flow: basic IF and WHILE working
- Function calls: missing
- Integration with Engine: partial

## Core Managers
### Base manager
- Service proxy classes: stable
- Event publish and subscribe: stable
### pixel_manager
- Core features: stable
- No interpolation between sprite positions
### Clock Manager
- Connection to NTP: stable
- Local Real Time Clock support
- Clock events for second, minute, hour day
### WiFi
- Core features: stable
- No support for re-connection if a network connection fails
- Only one set of WiFi settings supported
### MQTT 
- Setup and maintain an MQTT connection: stable
- Sending mqtt messages: stable
- Receiving MQTT messages: stable
- No manager binding to MQTT topics
- No support for secure sockets
### stepper_manager
- Core stepping: stable
- Timed moves: working
- Arc motion: working
## Graphics
- CoordMap: stable with direct buffer access
- Sprite: stable
- Frame: stable
- LightPanel: stable
- Text rendering: stable
- Animation framework stable but needing more animations
## Application Managers
### wordsearch_manager
- Clock mode: stable
- Animated display: stable
### blink_manager
- Basic version: stable

