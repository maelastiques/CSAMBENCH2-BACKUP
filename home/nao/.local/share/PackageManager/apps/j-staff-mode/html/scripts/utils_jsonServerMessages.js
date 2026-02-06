//////////////////////////////////////////
// Log functions
//////////////////////////////////////////

function socketlog(cls, line) {
	var dateObj = new Date();
	var timeStr = zeroFill(dateObj.getUTCHours(), 2) + ':' + zeroFill(dateObj.getUTCMinutes(), 2) + ':';
	timeStr += zeroFill(dateObj.getUTCSeconds(), 2) + '.' + zeroFill(dateObj.getUTCMilliseconds(), 3);
	var message = "[" + timeStr + "] " + line;
	// (this class often does not exist now)
	$("#dbgsocketlog").append('<div class="' + cls + '">' + message.slice(0, 100) + "</div>");
	if (console) {
		console.log(line)
	}
}

function socketlog_out(args) {
	if ((args[0] == "datafromrobotLog") || (args[0] == "datafromwebLog") || (args[0] == "tock") || (args[0] == "tablet/tick")) {
	}
	else if (args[0] == "datafromweb") {
		if (args[1].event != "tablet/tick") {
			socketlog("socketemit", '&lt;&lt; ' + args[1].event + ": " + args[1].data);
		}
	}
	else if (args[0] == "datafromrobot") {
		if (args[1].event != "tablet/tick") {
			socketlog("socketemit", '&lt;&lt; ' + args[1].event + ": " + args[1].data);
		}
	}
	else {
		socketlog("socketemit", '&lt;&lt; ' + Array.prototype.slice.call(args));
	}
}

function socketlog_in(args) {
	if ((args[0] == "datafromrobotLog") || (args[0] == "datafromwebLog") || (args[0] == "tock") || (args[0] == "tablet/tick")) {
	}
	else if (args[0] == "datafromrobot") {
		if (args[1].event != "tablet/tick") {
			socketlog("socketemit", '&gt&gt; ' + args[1].event + ": " + args[1].data);
		}
	}
	else {
		socketlog("socketon", '&gt&gt; ' + Array.prototype.slice.call(args));
	}
}

//////////////////////////////////////////
// Connection function
//////////////////////////////////////////

var g_socket = null;

var lastTickDate = -1;

$.connectSocketTo = function (ipAddr) {
	if (g_socket)
	{
		// first, disconnecting from the old IP address, connecting to new IP address!
		g_socket.emit("disconnect", {});
	}
	g_socket = io.connect(ipAddr + ":8000");

	// Test from http://stackoverflow.com/questions/8832414/overriding-socket-ios-emit-and-on/8838225
	// (this may not even be necessary, ther are some datafromwebLog and datafromrobotLog that seem
	// to contain the same info
	var emit = g_socket.emit;
	g_socket.emit = function() {
		socketlog_out(arguments);
		emit.apply(g_socket, arguments);
	};
	var $emit = g_socket.$emit;
	g_socket.$emit = function() {
		socketlog_in(arguments);
		$emit.apply(g_socket, arguments);
	};
	// end of tests
	
	// This can be done by QiMessaging: disable!
	// configure callbacks
	$.sendData = function(ALMemoryEvent, data){
		g_socket.emit("datafromweb", {"event": ALMemoryEvent, "data": data});	
	}
	
	// This cannot be done by QiMessaging yet: as soon as it can, this whole library can be dropped.
	$.recvData = function(JSEvent, callback){
		g_socket.on(JSEvent, function(data){
			callback(data);
		})
	}

	// If this isn't done, we won't be able to receive messages either.
	$.sendData("initConnection", "");
}


$(function () {
	if (isOnRobot()) {
		// 1) connect to robot!
		var robotHostname = location.hostname;
		$.connectSocketTo(robotHostname);
	
		// functions that could be in browser
		
		// This should be handled by the browser, but let's handle it here instead!
		$.recvData("setUrl", function(url){
			window.location.href = url;
		});
		
		$.recvData("setScenario", function(scenarioName){
			// This means a behavior asked for an 'old-style' scenario, that's hosted on the TTC server.
			var ttcIp = getQuery("ttcIp");
			if (ttcIp) {
				var robotHostname = location.hostname;
				var scenarioUrl = "http://" + ttcIp + ':8000/.framework/scenarioHome.html?ipAddr=' + robotHostname + '&app=' + scenarioName;
				window.location.href = scenarioUrl;
			}
		});
	}
});
