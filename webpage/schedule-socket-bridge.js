/**
 * Adapter for an EXISTING WebSocket. Never constructs/closes/reconnects a socket,
 * replaces on* handlers, retries sends, or uses legacy numeric command framing.
 * createPage(send) must construct the tested page binding without transport IO.
 * Forward send into its controllerOptions; the controller owns request deadlines.
 * attach(socket) accepts CONNECTING/OPEN sockets, detaches obsolete listeners and
 * invalidates the old page generation. Same-socket attach is idempotent.
 * Only scheduler replies are forwarded. Request/action/schema validation and capability
 * acceptance still belong to the real client/controller, not this bridge.
 * A false send or thrown socket.send means delivery uncertain; never retry here.
 */
(function(root, factory) {
	"use strict";
	if (typeof module === "object" && module.exports) module.exports = factory();
	else root.createWordclockScheduleSocketBridge = factory();
}(typeof window !== "undefined" ? window : this, function() {
	"use strict";
	return function(createPage) {
		if (typeof createPage !== "function") throw new Error("Page factory required");
		let active = null;
		let destroyed = false;
		function current(session) { return !destroyed && active === session; }
		function send(value, generation) {
			const session = active;
			if (destroyed || !session || !session.opened || session.socket.readyState !== 1 || typeof value !== "string" || !Number.isInteger(generation) || generation < 1) return false;
			// open() sends before returning its generation; bind it before send so
			// synchronous test replies cannot arrive with an uninitialized token.
			if (session.token === null) session.token = generation;
			if (session.token !== generation) return false;
			session.socket.send(value);
			return true;
		}
		const page = createPage(send);
		if (!page || ["open", "close", "receive", "snapshot", "refresh", "destroy"].some(function(name) { return typeof page[name] !== "function"; })) throw new Error("Complete page binding required");
		function detach() {
			const session = active;
			if (!session) return false;
			active = null;
			session.listeners.forEach(function(entry) { session.socket.removeEventListener(entry[0], entry[1]); });
			if (session.opened && session.token !== null) page.close(session.token);
			session.opened = false; session.token = null;
			return true;
		}
		return Object.freeze({
			attach: function(socket) {
				if (destroyed) throw new Error("Socket bridge destroyed");
				if (active && active.socket === socket) return false;
				if (!socket || ["addEventListener", "removeEventListener", "send"].some(function(name) { return typeof socket[name] !== "function"; }) || (socket.readyState !== 0 && socket.readyState !== 1)) throw new Error("Connecting or open socket required");
				detach();
				const session = { socket: socket, token: null, started: false, opened: false, listeners: [] };
				active = session;
				function opened() {
					if (!current(session) || session.started || socket.readyState !== 1) return;
					session.started = true; session.opened = true;
					const generation = page.open();
					if (current(session) && session.opened) session.token = generation;
				}
				function closed() {
					if (!current(session) || !session.opened) return;
					session.opened = false;
					const generation = session.token;
					session.token = null;
					if (generation !== null) page.close(generation);
				}
				function received(event) {
					if (!current(session) || !session.opened || session.token === null || socket.readyState !== 1 || typeof event.data !== "string") return;
					let reply;
					try { reply = JSON.parse(event.data); } catch (error) { if (error instanceof SyntaxError) return; throw error; }
					if (!reply || reply.command !== "brightness-schedule") return;
					page.receive(session.token, reply);
				}
				[["open", opened], ["close", closed], ["message", received]].forEach(function(entry) { socket.addEventListener(entry[0], entry[1]); session.listeners.push(entry); });
				if (socket.readyState === 1) opened();
				return true;
			},
			detach: detach,
			snapshot: function() { return page.snapshot(); },
			refresh: function() { if (!destroyed) page.refresh(); },
			destroy: function() {
				if (destroyed) return;
				destroyed = true;
				detach(); page.destroy();
			}
		});
	};
}));
