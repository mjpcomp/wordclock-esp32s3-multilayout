#!/usr/bin/env python3
"""Repair lint in the hash-verified phase-1 candidate, before tests/publication."""
from pathlib import Path
import hashlib

INPUT = {'webpage/script.js': 'f52855f85961b660e78164aa30d112940245e18128e83bae57328c6860aebfb7', 'webpage/i18n.js': 'e86dc60d12fc74d916d09f47bb8b3786178129e3a455bcd2f04fc4144bfa7e61'}
OUTPUT = {'webpage/script.js': '958cca95f2225fe6a6c891aaa96beecc51a1b9ba96c288610893c5692994bf3e', 'webpage/i18n.js': '7c35c5a3c79bbbabeb21759b9686b92b7a67c49c98b57c141292403d16844f1e'}
REFRESH = r"""function refreshConnectionText() {
	const state = websocket ? websocket.readyState : 3;
	const open = state === 1;
	const pending = state === 0;
	const closing = state === 2;
	let statusKey = "disconnected";
	let statusFallback = "Disconnected";
	if (open) {
		statusKey = "connected";
		statusFallback = "Connected";
	} else if (pending) {
		statusKey = "connecting";
		statusFallback = "Connecting…";
	} else if (closing) {
		statusKey = "disconnecting";
		statusFallback = "Disconnecting…";
	}
	const statusEl = document.getElementById("status");
	if (statusEl) {
		statusEl.classList.toggle("online", open);
		statusEl.classList.toggle("offline", !open);
		statusEl.value = connectionText(`settings.status.${statusKey}`, statusFallback);
	}
	document.querySelectorAll(".status-button").forEach(btn => {
		let key = "settings.status.connect";
		let fallback = "Connect";
		if (open) {
			key = "settings.status.disconnect";
			fallback = "Disconnect";
		} else if (pending) {
			key = "settings.status.connecting";
			fallback = "Connecting…";
		} else if (closing) {
			key = "settings.status.disconnecting";
			fallback = "Disconnecting…";
		} else if (btn.closest("#section-connection-lost")) {
			key = "connection-lost.button";
			fallback = "Reconnect";
		}
		btn.textContent = connectionText(key, fallback);
	});
}

window.refreshConnectionText = refreshConnectionText;
"""

def once(text,old,new):
 if text.count(old)!=1:raise ValueError('Missing/repeated lint-repair anchor')
 return text.replace(old,new,1)

def main():
 outputs={}
 for name,expected in INPUT.items():
  data=Path(name).read_bytes()
  if hashlib.sha256(data).hexdigest()!=expected:
   raise SystemExit('Unexpected phase-1 candidate: '+name)
  text=data.decode('utf-8')
  if name=='webpage/script.js':
   start=text.index('function refreshConnectionText() {')
   end=text.index('\nfunction handleConnectionButton()',start)
   text=text[:start]+REFRESH+text[end:]
   text=once(text,'/* eslint-disable no-console */\n','')
  else:
   text=once(text,'if (typeof refreshConnectionText === "function") refreshConnectionText();','if (typeof window.refreshConnectionText === "function") window.refreshConnectionText();')
  output=text.encode('utf-8')
  if hashlib.sha256(output).hexdigest()!=OUTPUT[name]:
   raise SystemExit('Unexpected lint-repair output: '+name)
  outputs[name]=output
 for name,data in outputs.items():Path(name).write_bytes(data)
 print('Applied hash-verified UI lint repair without weakening ESLint rules.')
if __name__=='__main__':main()
