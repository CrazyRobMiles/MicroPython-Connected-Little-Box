# Connected Little Box Messaging Guide

## Overview

This guide describes how CLB devices (called *boxes*) communicate with
each other using MQTT. Each box uses a simple, predictable addressing
system and can send commands to other boxes or receive commands itself.

## MQTT Topic Structure

### Device Topic

Every box listens on:

    <topicbase>/<devicename>

 `devicename` is initially generated from the device's unique ID. 

 `topicbase` initially set to the string `lb/clb`. You can edit these values at the command console using the `set` command:

    set mqtt_devicename=porch

The above command would set the devicename to "porch". You can also edit these setting values in the `settings.json` file on the device.


## Sending a Message

### Command Format

    mqtt.send <target_box_name> "<command>"

### Example

Send a pixel fill command to the box named *hallway*:

    mqtt.send hallway "pixel.fill 255 0 0"

This publishes the message to:

    /lb/clb/hallway

## Receiving a Message

When a box receives a message on its own topic:

    /lb/clb/<devicename>

The body of the message is executed as a **CLB command**.

### Example

If a box receives:

    pixel.fill 0 255 0

It behaves exactly as if the user typed the command locally.

## Common Examples

### Turn all boxes blue

If you know the names of your boxes:

    mqtt.send kitchen "pixel.fill 0 0 255"
    mqtt.send hallway "pixel.fill 0 0 255"
    mqtt.send porch "pixel.fill 0 0 255"

### Make a box reboot (if you have such a command)

    mqtt.send kitchen "system.reboot"

### Trigger a wordsearch animation

    mqtt.send lounge "wordsearch.show"

## Behaviour Summary

-   **Each box subscribes only to its own address.**
-   **Commands are executed exactly as if typed into the console.**
-   **Topic routing is always: `<topic_base>/<device_name>`.**
-   **Messaging is simple, human-readable, and easy to script.**

## Safety

Commands received over MQTT: - Have no additional validation. - Execute
immediately. Ensure your MQTT broker is not exposed publicly unless
secured properly.
