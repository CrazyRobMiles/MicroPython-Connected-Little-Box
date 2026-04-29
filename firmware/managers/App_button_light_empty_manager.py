from managers.base_manager import CLBAppManager


class Manager(CLBAppManager):
    version = "2.0.0"
    name = "Button Light Empty"
    file = "App_button_light_empty"
    desc = "Exercise 01 starting point — skeleton with no hardware attached"

    app_default_settings = {
        "App_button_light_empty": {
            "enabled": True,
            "dependencies": []
        }
    }

    def __init__(self, clb):
        super().__init__(clb)

    def setup(self, settings):
        super().setup(settings)
        if not self.enabled:
            self.state = self.STATE_DISABLED
            return
        self.state = self.STATE_OK
        self.set_status(1001, "Button Light ready")

    def update(self):
        if not self.enabled:
            return
