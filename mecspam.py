from halibot import CommandModule, Message, AsArgs
from halibot.jsdict import jsdict
import requests, os, json

url = "https://ffgupcomingapi.herokuapp.com/?root_collection=The%20Lord%20of%20the%20Rings:%20The%20Card%20Game"

class MecSpam(CommandModule):

	VERSION = "1.0.0"
	HAL_MINIMUM = "0.1"

	def init(self):
		self.config = jsdict(self.config)

		self.commands = {
			"spamfetch": self._spamfetch,
			"spamnick": self._spamnick,
			"spamcode": self._spamcode,
			"spamset": self._spamset,
			"spamreload": self._spamreload,
		}

		self.msg = None
		self.enabled = False

		if not self.config.get("codes"):
			self.config.codes = []
		if not self.config.get("nicks"):
			self.config.nicks = []
		if not self.config.get("delay"):
			self.config.delay = 60 * 60 * 12 # Twice a day should be fiiiine

		if not os.path.exists("spam-data.json"):
			self.data = {}
			self.do_update(msg=None)
		else:
			with open("spam-data.json", "r") as f:
				self.data = json.loads(f.read())

		if not self.name:
			for i in self._hal.objects.modules.items():
				if id(i[1]) == id(self):
					self.name = i[0]
					break


	def do_update(self, msg=None):
		r = requests.get(url)
		if not r.ok:
			self.log.warning("Failed to update!")
			return

		results = r.json().get("results")
		if not results:
			self.log.warning("Failed to parse results from json blob")
			return

		newdata = {x["product_code"]:x for x in filter(lambda x: x["product_code"] in self.config.codes, results) }

		updates = list(filter(lambda x: x["last_updated"] > self.data.get(x["product_code"], {"last_updated": 99999999999999})["last_updated"], newdata.values()))

		if updates or not msg:
			self.data = newdata
			with open("spam-data.json", "w") as f:
				f.write(json.dumps(self.data, indent=3))

		if msg:
			foo = {
				"in-stores": 0,
				"shipping": 1,
				"on-boat":2,
				"at-print":3,
				"in-dev":4,
				"awaiting-reprint":5,
			}
			updates = sorted(updates, key=lambda x: foo[x["css_class"]])
	
			i = 0	
			for u in updates:
				if i == 3 and len(updates[3:]):
					self.reply(msg, body="...and {} other updates".format(len(updates[3:])))
					break
				u["nicks"] = ", ".join(self.config.nicks)
				self.reply(msg, body="{nicks}: Product '{product_code} - {product}' has been updated to '{name}'".format(**u))
				i += 1



	def _spamfetch(self, _, msg=None):
		self.do_update(msg=None)

	@AsArgs
	def _spamnick(self, args, msg=None):
		nick = args[0]
		if nick in self.config.nicks:
			self.config.nicks.remove(nick)
			self.reply(msg, body="Nick '{}' has been removed from spamlist".format(nick))
			self.update_config()
			return

		self.config.nicks.append(nick)
		self.reply(msg, body="Added nick '{}' to spamlist".format(nick))
		self.update_config()


	@AsArgs
	def _spamcode(self, args, msg=None):
		code = args[0]
		op, code = code[0], code[1:]
		if op == "-":
			try:
				self.config.codes.remove(code)
			except:
				self.reply(msg, body="Could not remove code '{}', not currently watching for it".format(code))
				return
			self.reply(msg, body="No longer tracking updates to code '{}'".format(code))

		elif op == "+":
			if code in self.config.codes:
				self.reply(msg, body="Already tracking code '{}'".format(code))
				return
			self.config.codes.append(code)
			self.reply(msg, body="Now tracking updates to code '{}'".format(code))

		else:
			self.reply(msg, body="First character must be either + or - to indicate adding or removing to the list")
			return		
		self.update_config()

	def _spamset(self, _, msg=None):
		if self.enabled:
			self.enabled = False
			self.msg = None
			self.reply(msg, body="Disabled spammer")
			return
		self.msg = msg
		self.enabled = True

		self.reply(msg, body="Enabled spammer")
	
		self.eventloop.call_soon_threadsafe(self._looper)

	def _spamreload(self, _, msg=None):
		if os.path.exists("spam-data.json"):
			with open("spam-data.json", "r") as f:
				self.data = json.loads(f.read())

		self.reply(msg, body="Reloaded data from file, this may cause spam on the next update!")

	def _looper(self):
		if not self.enabled or not self.msg:
			return # We're done here

		self.do_update(msg=self.msg)	

		self.eventloop.call_soon_threadsafe(self.eventloop.call_later, self.config.delay, self._looper)

	def update_config(self):
		self._hal.config["module-instances"][self.name] = dict(self.config)
		if self._hal.VERSION == "0.2.0":
			self._hal._write_config()
		else:
			self.log.error("Cannot determine, or invalid halibot version to write back config, blame the developers")
