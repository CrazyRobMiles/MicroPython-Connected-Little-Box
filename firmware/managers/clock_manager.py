# /managers/clock_manager.py
from managers.base import CLBManager
from managers.event import Event
import time
import machine

try:
	import ntptime  # MicroPython NTP helper (sets RTC in UTC)
except ImportError:
	ntptime = None

class Manager(CLBManager):
	version = "1.0.0"
	dependencies = ["wifi"]  # wait for WiFi manager to be OK

	STATE_WAITING = "waiting"     # waiting for deps (WiFi)
	STATE_SYNCING = "syncing"     # actively doing NTP
	STATE_ERROR = "error"

	def __init__(self,clb):
		# tz_offset_minutes: simple fixed-offset timezone (DST can be handled by changing this value)
		# resync_minutes: how often to resync from NTP while online
		super().__init__(clb, defaults={
			"enabled": False,
			"ntpserver": "pool.ntp.org",
			"tz_offset_minutes": 0,
			"resync_minutes": 180,          # every 3 hours
			"sync_timeout_ms": 5000,        # informal budget; NTP has its own socket timeout
			"sync_on_start": True
		})

		self._next_sync_due_ms = 0
		self._last_sync_epoch_utc = 0
		self._have_ntp = (ntptime is not None)
		self._rtc = machine.RTC()

		# Define events owned by this manager
		self.events = {
			"clock.second": Event("clock.second", "Fired every second", self),
			"clock.minute": Event("clock.minute", "Fired every minute", self),
			"clock.hour":   Event("clock.hour",   "Fired every hour", self),
			"clock.day":    Event("clock.day",    "Fired every day", self),
		}

		self._last_second = None
		self._last_minute = None
		self._last_hour = None
		self._last_day = None

	# --- Utilities ----------------------------------------------------------

	def _now_epoch_utc(self) -> int:
		# After ntptime.settime(), time.time() is seconds since epoch in UTC
		try:
			return int(time.time())
		except Exception:
			return 0

	def _now_epoch_local(self) -> int:
		return self._now_epoch_utc() + int(self.settings.get("tz_offset_minutes", 0)) * 60

	def _iso_from_tuple(self, t):
		# t: localtime() or gmtime() 8-tuple
		y, m, d, hh, mm, ss, _, _ = t
		return f"{y:04d}-{m:02d}-{d:02d}T{hh:02d}:{mm:02d}:{ss:02d}"

	def _format_status_time(self):
		try:
			lt = time.localtime(self._now_epoch_local())
			return self._iso_from_tuple(lt)
		except Exception:
			return "unknown"

	def _schedule_next_sync(self):
		mins = int(self.settings.get("resync_minutes", 180))
		self._next_sync_due_ms = time.ticks_add(time.ticks_ms(), mins * 60_000)

	def _due_for_sync(self) -> bool:
		return time.ticks_diff(time.ticks_ms(), self._next_sync_due_ms) >= 0

	# --- CLB lifecycle ------------------------------------------------------

	def setup(self, settings):
		super().setup(settings)

		if not self.enabled:
			self.state = self.STATE_DISABLED
			return

		if not self._have_ntp:
			self.state = self.STATE_ERROR
			self.set_status(5000, "ntptime not available on this firmware")
			return

		# Start in waiting until WiFi is up
		self.state = self.STATE_WAITING
		self.set_status(5001, "Clock waiting for WiFi")

		# If requested, sync ASAP once WiFi comes up
		if self.settings.get("sync_on_start", True):
			self._next_sync_due_ms = time.ticks_ms()  # immediate
		else:
			self._schedule_next_sync()

	def update(self):
		if not self.enabled:
			return

		# If WiFi drops, go back to waiting (RTC keeps running, but we won't try NTP)
		if self.unresolved_dependencies():
			if self.state != self.STATE_WAITING:
				self.state = self.STATE_WAITING
				self.set_status(5002, "Clock paused (waiting for WiFi)")
			return

		# With WiFi available:
		if self.state in (self.STATE_WAITING, self.STATE_OK):
			if self._due_for_sync():
				self._attempt_sync()
			else:
				if self.state == self.STATE_WAITING:
					# No sync needed yet—still fine to operate off RTC
					self.state = self.STATE_OK
					self.set_status(5006, f"Clock running from RTC; next sync at ~{self._format_status_time()} local")

		elif self.state == self.STATE_SYNCING:
			# sync happens inline in _attempt_sync(); nothing to do here
			pass

		t = time.localtime(self._now_epoch_local())
		sec, minute, hour, day = t[5], t[4], t[3], t[2]

		if self._last_second != sec:
			self._last_second = sec
			self.events["clock.second"].publish({"time": t})

		if self._last_minute != minute:
			self._last_minute = minute
			self.events["clock.minute"].publish({"time": t})

		if self._last_hour != hour:
			self._last_hour = hour
			self.events["clock.hour"].publish({"time": t})

		if self._last_day != day:
			self._last_day = day
			self.events["clock.day"].publish({"time": t})

	def teardown(self):
		# Nothing persistent to close for RTC/NTP
		self.set_status(5019, "Clock manager torn down")

	# --- NTP & time access --------------------------------------------------

	def _attempt_sync(self):
		if not self._have_ntp:
			self.state = self.STATE_ERROR
			self.set_status(5003, "NTP not supported")
			return

		try:
			self.state = self.STATE_SYNCING
			host = self.settings.get("ntpserver", "pool.ntp.org") or "pool.ntp.org"
			ntptime.host = host
			self.set_status(5004, f"Syncing clock via NTP: {host}")
			ntptime.settime()  # sets RTC to UTC
			self._last_sync_epoch_utc = self._now_epoch_utc()
			self._schedule_next_sync()
			self.state = self.STATE_OK
			self.set_status(5005, f"Time synced. Local: {self._format_status_time()}")
		except Exception as e:
			# Keep running from RTC; try again later
			self.state = self.STATE_OK
			self._schedule_next_sync()
			self.set_status(5007, f"NTP sync failed; will retry later. {e}")

	# Public getters (for other managers / commands)
	def get_time_dict(self):
		"""Returns a dict with both UTC and local time values."""
		try:
			utc_epoch = self._now_epoch_utc()
			loc_epoch = self._now_epoch_local()

			u = time.gmtime(utc_epoch)
			l = time.localtime(loc_epoch)

			return {
				"utc_epoch": utc_epoch,
				"utc_iso": self._iso_from_tuple(u),
				"utc_tuple": u,
				"local_epoch": loc_epoch,
				"local_iso": self._iso_from_tuple(l),
				"local_tuple": l,
				"tz_offset_minutes": int(self.settings.get("tz_offset_minutes", 0)),
				"last_sync_epoch_utc": self._last_sync_epoch_utc,
				"state": self.state
			}
		except Exception as e:
			return {"error": str(e), "state": self.state}

	def get_time_tuple(self):
		"""Return (hour, minute, second)"""
		t = time.localtime()
		return (t[3], t[4], t[5])

	def get_date_tuple(self):
		"""Return (year, month, day)"""
		t = time.localtime()
		return (t[0], t[1], t[2])

	def get_datetime_string(self):
		"""Return formatted datetime for debugging"""
		t = time.localtime()
		return f"{t[2]:02d}/{t[1]:02d}/{t[0]} {t[3]:02d}:{t[4]:02d}:{t[5]:02d}"
	
	def get_interface(self):
		return {
			"on": ("Enable clock manager", self.command_enable),
			"off": ("Disable clock manager", self.command_disable),
			"now": ("Show current local and UTC time", self.command_now),
			"sync": ("Force an immediate NTP sync", self.command_sync),
			"utc": ("Show UTC epoch and ISO time", self.command_utc),
			"local": ("Show local epoch and ISO time", self.command_local),
			"time":("Get time tuple", self.get_time_tuple),
			"date":("Get date tuple", self.get_date_tuple),
			"string":("Get date string", self.get_datetime_string)
		}

	def command_enable(self):
		self.enabled = True
		self.set_status(5010, "Clock manually enabled")
		self.setup(self.settings)

	def command_disable(self):
		self.enabled = False
		self.state = self.STATE_DISABLED
		self.set_status(5011, "Clock manually disabled")

	def command_now(self):
		t = self.get_time_dict()
		if "error" in t:
			self.set_status(5012, f"Clock error: {t['error']}")
		else:
			self.set_status(
				5013,
				f"Local {t['local_iso']} (UTC{t['tz_offset_minutes']:+d}m) | UTC {t['utc_iso']}"
			)

	def command_sync(self):
		if self.unresolved_dependencies():
			self.set_status(5014, "Cannot sync: WiFi not ready")
			return
		self._next_sync_due_ms = time.ticks_ms()  # make it due now
		self._attempt_sync()

	def command_utc(self):
		t = self.get_time_dict()
		if "error" in t:
			self.set_status(5015, f"UTC error: {t['error']}")
		else:
			self.set_status(5016, f"UTC: {t['utc_epoch']} ({t['utc_iso']})")

	def command_local(self):
		t = self.get_time_dict()
		if "error" in t:
			self.set_status(5017, f"Local error: {t['error']}")
		else:
			self.set_status(5018, f"Local: {t['local_epoch']} ({t['local_iso']})")

	# --- Event publishers --------------------------------------------------

	def _fire_second_event(self, t):
		self.clb.publish("clock.second", t)

	def _fire_minute_event(self, t):
		self.clb.publish("clock.minute", t)

	def _fire_hour_event(self, t):
		self.clb.publish("clock.hour", t)

	def _fire_day_event(self, t):
		self.clb.publish("clock.day", t)
