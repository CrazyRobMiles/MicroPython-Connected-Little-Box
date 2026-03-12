# /managers/clock_manager.py
from managers.base_manager import CLBManager
from managers.event import Event
import time
import machine
import socket
import struct

# NTP constants
_NTP_EPOCH_DELTA = 2208988800  # seconds between 1900 and 1970
_SAKAMOTO_T = (0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4)
_LONG_MONTHS = (1, 3, 5, 7, 8, 10, 12)

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
  
class _UKDST:
	"""
	UK daylight saving (BST) rules, expressed in UTC:
	- Starts: last Sunday in March at 01:00 UTC
	- Ends:   last Sunday in October at 01:00 UTC
	"""
	def __init__(self):
		self._year = None
		self._start_utc = 0
		self._end_utc = 0

	@staticmethod
	def _is_leap(year: int) -> bool:
		return (year % 4 == 0) and ((year % 100 != 0) or (year % 400 == 0))

	@classmethod
	def _days_in_month(cls, year: int, month: int) -> int:
		if month == 2:
			return 29 if cls._is_leap(year) else 28
		if month in _LONG_MONTHS:
			return 31
		return 30

	@staticmethod
	def _weekday_mon0(year: int, month: int, day: int) -> int:
		"""
		Monday=0 .. Sunday=6
		(Sakamoto algorithm)
		"""
		y = year
		if month < 3:
			y -= 1
		# Sakamoto yields Sunday=0..Saturday=6
		w = (y + y // 4 - y // 100 + y // 400 + _SAKAMOTO_T[month - 1] + day) % 7
		# Convert to Monday=0..Sunday=6
		return (w - 1) % 7

	@classmethod
	def _last_sunday(cls, year: int, month: int) -> int:
		last_day = cls._days_in_month(year, month)
		wd = cls._weekday_mon0(year, month, last_day)  # Mon=0..Sun=6
		# step back to Sunday (6)
		delta = (wd - 6) % 7
		return last_day - delta

	@staticmethod
	def _epoch_utc_for(y: int, m: int, d: int, hh: int, mm: int, ss: int) -> int:
		# Assumes device clock (time.time()) is UTC, as per your NTP sync code.
		return int(time.mktime((y, m, d, hh, mm, ss, 0, 0)))

	def _compute_year(self, year: int):
		d_start = self._last_sunday(year, 3)
		self._start_utc = self._epoch_utc_for(year, 3, d_start, 1, 0, 0)

		d_end = self._last_sunday(year, 10)
		self._end_utc = self._epoch_utc_for(year, 10, d_end, 1, 0, 0)

		self._year = year

	def is_dst(self, epoch_utc: int) -> bool:
		y = time.gmtime(epoch_utc)[0]
		if y != self._year:
			self._compute_year(y)
		return (epoch_utc >= self._start_utc) and (epoch_utc < self._end_utc)

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
			"sync_on_start": True,
			"dst_uk_enabled": True,
			"dst_uk_delta_minutes": 60
   		})

		self._rtc = machine.RTC()
		self._ukdst = _UKDST()
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
		epoch_utc = self._now_epoch_utc()

		offset = int(self.settings.get("tz_offset_minutes", 0)) * 60

		if self.settings.get("dst_uk_enabled", True):
			if self._ukdst.is_dst(epoch_utc):
				offset += int(self.settings.get("dst_uk_delta_minutes", 60)) * 60

		return epoch_utc + offset

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
		"""
		Return local (DST-corrected) time tuple:
		(hour, minute, second)
		"""
		t = time.gmtime(self._now_epoch_local())
		return t[3], t[4], t[5]

	def get_date_tuple(self):
		"""
		Return local (DST-corrected) date tuple:
		(year, month, day)
		"""
		t = time.gmtime(self._now_epoch_local())
		return t[0], t[1], t[2]

	def get_interface(self):
		return {
			"on":   ("Enable clock manager", self.command_enable),
			"off":  ("Disable clock manager", self.command_disable),
			"sync": ("Force async NTP sync", self.command_sync),
			"time": ("Get time tuple", self.get_time_tuple),
			"date": ("Get date tuple", self.get_date_tuple	),
			"dst_test": ("Test UK DST transitions", self.command_test_dst_uk)
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

	def command_test_dst_uk(self, year=None):
		"""
		Deterministic DST proof test for UK (BST/GMT):
		- Start: last Sunday in March at 01:00 UTC  (offset becomes +3600)
		- End:   last Sunday in October at 01:00 UTC (offset becomes +0)
		This test does NOT depend on current time.
		"""
		try:
			year = int(year) if year is not None else time.gmtime()[0]
		except Exception:
			year = time.gmtime()[0]

		# --- helpers (self-contained) ---
		def is_leap(y):
			return (y % 4 == 0) and ((y % 100 != 0) or (y % 400 == 0))

		def dim(y, m):
			if m == 2:
				return 29 if is_leap(y) else 28
			if m in (1, 3, 5, 7, 8, 10, 12):
				return 31
			return 30

		def weekday_mon0(y, m, d):
			# Monday=0..Sunday=6 (Sakamoto)
			t = [0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4]
			yy = y - 1 if m < 3 else y
			w = (yy + yy // 4 - yy // 100 + yy // 400 + t[m - 1] + d) % 7  # Sunday=0..Sat=6
			return (w - 1) % 7  # Monday=0..Sunday=6

		def last_sunday(y, m):
			ld = dim(y, m)
			wd = weekday_mon0(y, m, ld)  # Mon=0..Sun=6
			delta = (wd - 6) % 7         # step back to Sunday
			return ld - delta

		def epoch_utc_for(y, m, d, hh, mm, ss):
			# Assumes your RTC/NTP time base is UTC, which is how your sync code sets RTC :contentReference[oaicite:1]{index=1}
			return int(time.mktime((y, m, d, hh, mm, ss, 0, 0)))

		# Compute transition instants in UTC
		mar_day = last_sunday(year, 3)
		oct_day = last_sunday(year, 10)
		dst_start_utc = epoch_utc_for(year, 3, mar_day, 1, 0, 0)
		dst_end_utc   = epoch_utc_for(year, 10, oct_day, 1, 0, 0)

		# Probe instants around transitions
		probes = [
			("START-1s", dst_start_utc - 1, 0),
			("START+0s", dst_start_utc + 0, 3600),
			("START+1s", dst_start_utc + 1, 3600),
			("END-1s",   dst_end_utc - 1,   3600),
			("END+0s",   dst_end_utc + 0,   0),
			("END+1s",   dst_end_utc + 1,   0),
		]

		# Monkeypatch _now_epoch_utc so we drive _now_epoch_local deterministically
		orig_now_utc = self._now_epoch_utc

		def check_at(epoch_utc, expected_extra):
			self._now_epoch_utc = lambda: epoch_utc
			local_epoch = self._now_epoch_local()
			# base offset is whatever tz_offset_minutes is set to (UK winter should be 0)
			base = int(self.settings.get("tz_offset_minutes", 0)) * 60
			extra = local_epoch - epoch_utc - base
			ok = (extra == expected_extra)

			u = time.gmtime(epoch_utc)
			l = time.gmtime(local_epoch)  # local_epoch is "UTC+offset", so gmtime shows the shifted wall time
			print("[DST_TEST]",
				"UTC %04d-%02d-%02d %02d:%02d:%02d" % (u[0], u[1], u[2], u[3], u[4], u[5]),
				"-> LOCAL %04d-%02d-%02d %02d:%02d:%02d" % (l[0], l[1], l[2], l[3], l[4], l[5]),
				"extra=%d expected=%d %s" % (extra, expected_extra, "OK" if ok else "FAIL"))
			return ok

		try:
			print("[DST_TEST] Year:", year)
			print("[DST_TEST] UK DST starts (UTC):", time.gmtime(dst_start_utc))
			print("[DST_TEST] UK DST ends   (UTC):", time.gmtime(dst_end_utc))

			all_ok = True
			for tag, e, expected in probes:
				ok = check_at(e, expected)
				if not ok:
					all_ok = False

			print("[DST_TEST] RESULT:", "PASS" if all_ok else "FAIL")
		finally:
			self._now_epoch_utc = orig_now_utc
