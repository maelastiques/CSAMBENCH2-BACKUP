/**********************************************************************
 * This logs to QiMessaging, and adds a few useful functions to the
 * JQuery namespace.
 *********************************************************************/

$(function () {
	if (isOnRobot()) {
		$.qim = new QiSession("http://" + window.location.host, "libs/qimessaging/1.0/socket.io");

		$.qim.socket().on('connect', function() {
			if (console) {
				console.log('Qimessaging: connected!');
			}
		});

		$.qim.socket().on('disconnect', function() {
			if (console) {
				console.log('Qimessaging: disconnected!');
			}
		});

		$.onQimError = function (data) {
			if (console) {
				console.log("Service error: " + data);
			}
		}
		
		// A helper function that just makes some syntax shorter (to avoid adding fail handlers all the time)
		$.getService = function(serviceName, doneCallback) {
			return $.qim.service(serviceName).done(doneCallback).fail(function (data) {
				if (console) {
					console.log("Failed getting " + serviceName + ": " + data);
				}
			});
		}
		
		// Since ALMemory is frequently used, you can raise events with this.
		$.raiseALMemoryEvent = function(event, value) {
			return $.getService("ALMemory", function(ALMemory) {
				ALMemory.raiseEvent(event, value).fail($.onQimError);
			});
		}
	} else {
		// No robot
		$.raiseALMemoryEvent = function(event, value) {};

	}
});
