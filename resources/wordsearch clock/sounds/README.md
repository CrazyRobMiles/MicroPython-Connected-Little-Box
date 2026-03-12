# Alarm Sounds

The sounds for the alarm clock are stored on a MicroSD card which is fitted inside the DFPlayer. The DFPlayer does not use the filenames to access sound files, instead it uses the absolute numbers of the files on the card. When you ask it to play file 1 it will play the first file loaded onto the card, and so on. 

The first two files on the card are the alarm off (file 1) and alarm on (file 2) messages. These are played when the user toggles the alarm status. The remaining files are all different alarm sound messages. When the alarm is triggered it picks a random sound and plays that. There are two sets of alarm messages in this repository. The **tones** folder contains a set of alarm tones. The **voice** folder contains a set of alarm voice messages. 

If you make your own alarm clock you will need to copy the sound files onto an SD card, making sure that you copy the alarm off and alarm on messages first. Then copy as many of the different voice and tone files (along with your own) as you like. Once you have done this you need to tell the alarm clock the number of voice files you have created so that it can pick random ones correctly. You do this by editing a setting in the **settings.json** file in the firmware folder:

```json
    "App_wordsearch_alarmclock": {
        "number_of_audio_tracks": 54,
```

Find the settings for **App_wordsearch_alarmclock** and then set the value of **number_of_audio_tracks** to match the number of sound files on the MicroSD card. 

[Resources Home](../README.md)