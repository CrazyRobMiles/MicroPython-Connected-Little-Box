# /managers/clock_manager.py
from managers.base import CLBManager
from managers.event import Event
import time
import machine
import socket
import struct

# NTP constants
_NTP_EPOCH_DELTA = 2208988800  # seconds between 1900 and 1970

class _AsyncNTP:
	"""
	Robust async-ish NTP client for MicroPython.
	Uses short socket timeouts instead of true non-blocking mode.
	"""
	def __init__(self, host, timeout_ms=3000):
		self.host = host
		self.timeout_ms = timeout_ms
		self.sock = None
		self.addr = None
		self.start_ms = 0
		self.epoch_utc = None
		self.done = False

	def start(self):
		import socket
		import time

		self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.sock.settimeout(0.1)   # IMPORTANT: not 0
		self.addr = socket.getaddrinfo(self.host, 123)[0][-1]

		pkt = bytearray(48)
		pkt[0] = 0x1B  # NTP client request

		self.sock.sendto(pkt, self.addr)
		self.start_ms = time.ticks_ms()

	def poll(self):
		import time
		import struct

		if self.done:
			return True

		# overall timeout
		if time.ticks_diff(time.ticks_ms(), self.start_ms) > self.timeout_ms:
			self._close()
			self.done = True
			return False

		try:
			data, _ = self.sock.recvfrom(48)
			if data and len(data) >= 48:
				secs = struct.unpack("!I", data[40:44])[0]
				self.epoch_utc = secs - 2208988800
				self._close()
				self.done = True
				return True
		except OSError:
			# no data yet
			pass

		return None

	def _close(self):
		try:
			self.sock.close()
		except Exception:
			pass
		self.sock = None

class Manager(CLBManager):
	version = "1.1.0"
	dependencies = ["wifi"]

	STATE_WAITING  = "waiting"
	STATE_SYNCING  = "syncing"
	STATE_ERROR    = "error"

	def __init__(self, clb):
		super().__init__(clb, defaults={
			"enabled": False,
			"ntpserver": "129.6.15.28",   # numeric by default (no DNS stall)
			"tz_offset_minutes": 0,
			"resync_minutes": 180,
			"sync_timeout_ms": 2000,
			"sync_on_start": True
		})

		self._rtc = machine.RTC()
		self._ntp = None
		self._next_sync_due_ms = 0
		self._last_sync_epoch_utc = 0

		# Event ownership
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

	# ------------------------------------------------------------------
	# Time helpers
	# ------------------------------------------------------------------

	def _now_epoch_utc(self):
		try:
			return int(time.time())
		except Exception:
			return 0

	def _now_epoch_local(self):
		return self._now_epoch_utc() + int(self.settings["tz_offset_minutes"]) * 60

	def _schedule_next_sync(self):
		mins = int(self.settings["resync_minutes"])
		self._next_sync_due_ms = time.ticks_add(
			time.ticks_ms(), mins * 60_000
		)

	def _due_for_sync(self):
		return time.ticks_diff(time.ticks_ms(), self._next_sync_due_ms) >= 0

	# ------------------------------------------------------------------
	# Lifecycle
	# ------------------------------------------------------------------

	def setup(self, settings):
		super().setup(settings)

		if not self.enabled:
			self.state = self.STATE_DISABLED
			return

		self.state = self.STATE_WAITING
		self.set_status(5001, "Clock waiting for WiFi")

		if self.settings.get("sync_on_start", True):
			self._next_sync_due_ms = time.ticks_ms()
		else:
			self._schedule_next_sync()

	def update(self):
		if not self.enabled:
			return

		# Dependency gate
		if self.unresolved_dependencies():
			if self.state != self.STATE_WAITING:
				self.state = self.STATE_WAITING
				self.set_status(5002, "Clock paused (waiting for WiFi)")
			return

		# Start async NTP if due
		if self.state in (self.STATE_WAITING, self.STATE_OK):
			if self._due_for_sync() and self._ntp is None:
				self._start_async_sync()

		# Poll async NTP
		if self.state == self.STATE_SYNCING and self._ntp:
			result = self._ntp.poll()

			if result is True:
				t = time.gmtime(self._ntp.epoch_utc)

				# RTC expects: (year, month, day, weekday, hour, minute, second, subseconds)
				self._rtc.datetime((
					t[0],  # year
					t[1],  # month
					t[2],  # day
					t[6],  # weekday (0=Monday)
					t[3],  # hour
					t[4],  # minute
					t[5],  # second
					0       # subseconds
				))
				self._last_sync_epoch_utc = self._ntp.epoch_utc
				self._schedule_next_sync()
				self._ntp = None
				self.state = self.STATE_OK
				self.set_status(5005, "Time synced (async NTP)")

			elif result is False:
				self._schedule_next_sync()
				self._ntp = None
				self.state = self.STATE_OK
				self.set_status(5007, "Async NTP failed; retry later")

		# Emit clock events (RTC always runs)
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
		self._ntp = None
		self.set_status(5019, "Clock manager torn down")

	# ------------------------------------------------------------------
	# Async NTP start
	# ------------------------------------------------------------------

	def _start_async_sync(self):
		try:
			self.state = self.STATE_SYNCING
			self._ntp = _AsyncNTP(
				self.settings["ntpserver"],
				self.settings["sync_timeout_ms"]
			)
			self._ntp.start()
			self.set_status(5004, f"Async NTP request sent to {self.settings['ntpserver']}")
		except Exception as e:
			self.state = self.STATE_OK
			self._ntp = None
			self._schedule_next_sync()
			self.set_status(5007, f"NTP init failed: {e}")

	# ------------------------------------------------------------------
	# Public API
	# ------------------------------------------------------------------

	def get_time_tuple(self):
		t = time.localtime(self._now_epoch_local())
		return (t[3], t[4], t[5])

	def get_interface(self):
		return {
			"on":   ("Enable clock manager", self.command_enable),
			"off":  ("Disable clock manager", self.command_disable),
			"sync": ("Force async NTP sync", self.command_sync),
			"time": ("Get time tuple", self.get_time_tuple),
		}

	def command_enable(self):
		self.enabled = True
		self.setup(self.settings)

	def command_disable(self):
		self.enabled = False
		self.state = self.STATE_DISABLED
		self.set_status(5011, "Clock manually disabled")

	def command_sync(self):
		if self.unresolved_dependencies():
			self.set_status(5014, "Cannot sync: WiFi not ready")
			return
		self._next_sync_due_ms = time.ticks_ms()
