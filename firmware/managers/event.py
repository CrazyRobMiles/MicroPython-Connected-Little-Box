# event.py or inside clb.py

try:
    import time
    ticks = time.time
except:
    import time
    ticks = time.ticks_ms

class Event:
    """
    Represents a single published event owned by a manager.
    Multiple subscribers can attach to a single Event.
    """
    def __init__(self, name, description, owner):
        self.name = name
        self.description = description
        self.owner = owner  # Manager that owns this event
        self.subscribers = []   # list of subscription dicts

    def subscribe(self, callback, **options):
        """
        Subscribe a callback to this event.

        Supported options:
            interval = seconds between firing
            once     = unsubscribe after first call
            filter   = callable(event, data) -> bool
        """
        self.subscribers.append({
            "cb": callback,
            "options": options,
            "last": 0
        })

    def unsubscribe(self, callback):
        self.subscribers = [
            s for s in self.subscribers if s["cb"] is not callback
        ]

    def publish(self, data=None):
        """
        Publish this event to all subscribers.
        Handles throttling, filtering, generator callbacks,
        and StopIteration auto-unsubscribe.
        """
        now = ticks()
        survivors = []

        for sub in self.subscribers:
            cb = sub["cb"]
            opts = sub["options"]
            last = sub["last"]

            # interval throttling
            interval = opts.get("interval")
            if interval is not None and (now - last) < interval:
                survivors.append(sub)
                continue

            # optional filter predicate
            predicate = opts.get("filter")
            if predicate and not predicate(self, data):
                survivors.append(sub)
                continue

            # call handler
            try:
                if hasattr(cb, "send"):  # generator-based
                    cb.send((self, data))
                else:
                    cb(self, data)

                sub["last"] = now

                # keep if not once=True
                if not opts.get("once"):
                    survivors.append(sub)

            except StopIteration:
                # generator finished
                pass
            except Exception as e:
                print("Event handler error:", e)
                survivors.append(sub)

        self.subscribers = survivors
