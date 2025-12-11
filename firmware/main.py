version = "1.0.0"

from device_configurator import DeviceConfigurator

from clb import CLB

debug=True

config = DeviceConfigurator(
    settings_file="settings.json",
    safe_pin=-1,
    use_obfuscation=False
)

if not config.setup(force_online=False):
    config.setup(force_online=True)

clb = CLB(config)

clb.setup()

clb.describe()

if debug:
    while clb.running:
        clb.update()
        clb.update_console()
else:
    try:
        while clb.running:
            clb.update()
            clb.update_console()
    except Exception as e:
        print(e)
        clb.teardown()
 
 