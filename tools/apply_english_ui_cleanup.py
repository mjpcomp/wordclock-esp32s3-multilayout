#!/usr/bin/env python3
"""Guarded English UI migration. Validate every input before writing any file."""
from pathlib import Path
import hashlib
import json

INPUT = {'webpage/script.js': '3f8d7ad89278f04d97afda569a31a24e640075170b34af90c53b123c6362f1c5', 'webpage/language/en.js': 'bd0df9148af6b09f13c1af50f8c29384cf1f6255c2fc02aa89f2f909c808616a', 'webpage/i18n.js': 'be7eed9adec9bd96d79b0af71a1100a5da78ccb4ff5de96b6d371ac39eb9936d'}
OUTPUT = {'webpage/script.js': 'f52855f85961b660e78164aa30d112940245e18128e83bae57328c6860aebfb7', 'webpage/language/en.js': '0238f54c773223b8f8be3a0626182eebf686d6a43e627e439254642d365ea233', 'webpage/i18n.js': 'e86dc60d12fc74d916d09f47bb8b3786178129e3a455bcd2f04fc4144bfa7e61'}
HELPER = r"""function connectionText(key, fallback) {
	if (typeof i18next === "undefined" || !i18next.isInitialized) return fallback;
	return i18next.t(key, { defaultValue: fallback });
}

function refreshConnectionText() {
	const state = websocket ? websocket.readyState : 3;
	const open = state === 1;
	const pending = state === 0;
	const closing = state === 2;
	const statusEl = document.getElementById("status");
	if (statusEl) {
		statusEl.classList.toggle("online", open);
		statusEl.classList.toggle("offline", !open);
		statusEl.value = open ? connectionText("settings.status.connected", "Connected")
			: pending ? connectionText("settings.status.connecting", "Connecting…")
			: closing ? connectionText("settings.status.disconnecting", "Disconnecting…")
			: connectionText("settings.status.disconnected", "Disconnected");
	}
	document.querySelectorAll(".status-button").forEach(btn => {
		btn.textContent = open ? connectionText("settings.status.disconnect", "Disconnect")
			: pending ? connectionText("settings.status.connecting", "Connecting…")
			: closing ? connectionText("settings.status.disconnecting", "Disconnecting…")
			: btn.closest("#section-connection-lost")
				? connectionText("connection-lost.button", "Reconnect")
				: connectionText("settings.status.connect", "Connect");
	});
}

function handleConnectionButton() {
	if (this.value === "1") {
		document.querySelectorAll(".status-button").forEach(btn => { btn.value = "0"; });
		if (websocket) websocket.close();
	} else {
		document.querySelectorAll(".status-button").forEach(btn => { btn.value = "1"; });
		initWebsocket();
	}
	refreshConnectionText();
}

"""
ENGLISH = [('title', 'Wordclock', 'Word Clock'), ('wordclock', 'Wordclock', 'Word Clock'), ('scrollingtext', 'Scrollingtext', 'Scrolling text'), ('button', 'Connect', 'Reconnect'), ('text', 'The connection to the Word Clock has been lost.', 'Connection to the Word Clock lost. Select Reconnect to try again.'), ('variant', 'Choice of Clock Variant', 'Clock layout'), ('h2', 'Front', 'Clock face'), ('buildtype', 'Buildtype', 'LED arrangement'), ('meander-rows', 'Rows placed in meanders', 'Serpentine row wiring'), ('hide-it-is', "„Display 'It is'“", 'Show “It is”'), ('it-is-permanent', 'Permanent', 'Always'), ('it-is-quarterly', 'Quarterly', 'Every 15 minutes'), ('it-is-half-hourly', 'Half-hourly', 'Every 30 minutes'), ('it-is-hourly', 'Hourly', 'Every hour'), ('in-border', 'Seconds in the Border', 'Show seconds around the frame'), ('label', 'Change of Color Type', 'Color order'), ('h2', 'Timezone', 'Time zone'), ('label', 'POSIX timezone', 'Time zone rule (advanced)'), ('other-wifi', 'Other Wi-Fi', 'Change Wi-Fi network'), ('until-restart', 'Until Restart', 'Disable Wi-Fi until restart'), ('deactivate', 'Deactivate', 'Disable Wi-Fi'), ('restart', 'Reset to Default Values', 'Save current settings'), ('reset', 'Restart', 'Restart clock'), ('discovery', 'Send HA Discovery', 'Publish Home Assistant discovery')]

def once(text, old, new):
 if text.count(old)!=1:raise ValueError('Missing/repeated reviewed anchor: '+repr(old))
 return text.replace(old,new,1)

def quoted(key,value):
 return json.dumps(key,ensure_ascii=False)+': '+json.dumps(value,ensure_ascii=False)

def migrate(name,text):
 if name=='webpage/script.js':
  text=once(text,'function initWebsocket() {',HELPER+'function initWebsocket() {')
  text=once(text,'websocket = new WebSocket(ipEsp);','websocket = new WebSocket(ipEsp);\n\trefreshConnectionText();')
  for event,value in [('onopen','1'),('onclose','0')]:
   start=text.index('\t\tconst statusEl',text.index('websocket.'+event+' ='))
   end=text.index('\t\tconst connLostEl',start)
   replacement='\t\tdocument.querySelectorAll(".status-button").forEach(btn => { btn.value = "'+value+'"; });\n\t\trefreshConnectionText();\n\n'
   text=once(text,text[start:end],replacement)
  start=text.index('\tdocument.querySelectorAll(".status-button").forEach',text.index('document.addEventListener("DOMContentLoaded"'))
  end=text.index('\tconst clockBtn',start)
  text=once(text,text[start:end],'\tdocument.querySelectorAll(".status-button").forEach(btn => {\n\t\tbtn.addEventListener("click", handleConnectionButton);\n\t});\n\n')
  text=once(text,'document.getElementById("wlanlist").innerHTML = "<div>WLAN Netzwerke werden gesucht</div>";','document.getElementById("wlanlist").textContent = connectionText("settings.wifi.scanning", "Scanning for Wi-Fi networks…");')
  text=once(text,'let debugMessageReconfigured = " was reconfigured.";','let debugMessageReconfigured = " change requested.";')
  for old,new in [('Timeserver','NTP server'),('ScrollingText','Scrolling text')]:
   text=once(text,old+'${debugMessageReconfigured}',new+'${debugMessageReconfigured}')
  for old,new in [('The connection with the websocket has been established.','WebSocket connected.'),('The connection with the websocket was closed (code ${event.code}).','WebSocket disconnected (code ${event.code}).'),('An error occurred while connecting to the websocket.','WebSocket connection failed.')]:
   text=once(text,old,new)
 elif name=='webpage/i18n.js':
  text=once(text,'}\n\nfunction initLanguageDropdown(language) {','\tif (typeof refreshConnectionText === "function") refreshConnectionText();\n}\n\nfunction initLanguageDropdown(language) {')
 elif name=='webpage/language/en.js':
  for old,new in [('"Reconfiguration creates its own wireless network.\\n " +\n\t\t\t\t"Connect to this temporary network, then the target network can be selected."', '"The clock starts a temporary setup Wi-Fi network. Connect to it to choose the Wi-Fi network the clock should join."'), ('"text": "The software of the Word Clock can be controlled using MQTT. Here you can integrate the clock via your existing Home Assistant setup in order to be able to control rudimentary functions."', '"text": "Control supported clock functions through MQTT and integrate the clock with Home Assistant."')]:text=once(text,old,new)
  for key,old,new in ENGLISH:text=once(text,quoted(key,old),quoted(key,new))
  for key,t in [('at-nine-fifteen','9:15'),('at-nine-twenty','9:20'),('at-nine-fourty','9:40'),('at-nine-fourtyfive-german','9:45'),('at-nine-fourtyfive-english','9:45')]:
   text=once(text,quoted(key,'On '+t+' It Is ...'),quoted(key,'At '+t+', display…'))
  for old,new in [('Save Setting','Save'),('Time Server','NTP server')]:
   text=text.replace(json.dumps(old),json.dumps(new))
  text=once(text,quoted('connect','Connect'),quoted('connect','Connect')+',\n\t\t\t"connected": "Connected",\n\t\t\t"disconnected": "Disconnected",\n\t\t\t"connecting": "Connecting…",\n\t\t\t"disconnecting": "Disconnecting…",\n\t\t\t"disconnect": "Disconnect"')
  text=once(text,quoted('configure','Configure'),quoted('configure','Configure')+',\n\t\t\t"scanning": "Scanning for Wi-Fi networks…"')
 else:raise ValueError('Unreviewed file: '+name)
 return text

def main():
 outputs={}
 for name,expected in INPUT.items():
  data=Path(name).read_bytes()
  if hashlib.sha256(data).hexdigest()!=expected:
   raise SystemExit('Unexpected UI source; refusing all edits: '+name)
  output=migrate(name,data.decode('utf-8')).encode('utf-8')
  if hashlib.sha256(output).hexdigest()!=OUTPUT[name]:
   raise SystemExit('Unexpected UI output; refusing all edits: '+name)
  outputs[name]=output
 for name,data in outputs.items():Path(name).write_bytes(data)
 print('Applied reviewed English UI cleanup to exactly three source files.')
if __name__=='__main__':main()
