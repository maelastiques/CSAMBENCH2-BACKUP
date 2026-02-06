$(function () {
	// registration could be called automatically from the widget code itself.
	function insertTrayWidget(widgetUrl, buttonState, iconState) {
		$.get(widgetUrl,
			"", // no data
			function(widgetHtml) {
				var widgetDiv = $(widgetHtml);
				$("#hidden-tray").append(widgetDiv); // At this point, the code in the widget is called.
				widgetDiv.registerWidget(); // Pretty much a custom constructor, adds callbacks, etc.
				setTrayWidgetState($(widgetDiv).data("name"), buttonState, iconState);
			}, "text");
	}
	
	function setTrayWidgetState(widgetName, buttonState, iconState) {
		//log("[DBG] Setting " + widgetName + " to buttonState: " + buttonState + " and iconState: " + iconState);
		var trayWidget = $("#" + widgetName + "-traywidget"); // (they could be registered somewhere, but this is simpler)
		if (buttonState) {
			trayWidget.setButtonState(buttonState);
		}
		if (iconState) {
			trayWidget.setIconState(iconState);
		}
	}

	// Top right tray handling
	$("#corner-button").mousedown(function() {
		var unfoldingTab = $("#corner-unfolded-button");
		if (!unfoldingTab.is(":visible")) {
			$("#corner-button").hide();
			unfoldingTab.show();
			event.stopPropagation();
			// To hide it, click anywhere.
		}
	});
	
	$("#corner-unfolded-button").mousedown(function(event) {
		event.stopPropagation();
	});
	
	$('html').mousedown(function() {
		var unfoldingTab = $("#corner-unfolded-button");
		if (unfoldingTab.is(":visible")) {
			unfoldingTab.hide();
			$("#corner-button").show();
		} 
	});

	
	$("#exit-button").mousedown(function(event) {
		loadFragment("");
		createStandardWidgets();
		if (!isOnRobot()) {
			$("#debugsplash").show();
		}
		$("#wizard-tray").hide();
		$("#widget-tray").hide();
		$("#corner-button").hide();
		$("#corner-unfolded-button").hide();
		$.raiseALMemoryEvent("BootConfig/exitMenu", "exitMenu");
		event.stopPropagation();
		//event.stopPropagation(); // This is the only button that doesn't close the menu
	});

	// Wizard handling
	var g_wizardFragments = [];
	var g_posInWizard = 0;

	// Auto widget creation (could be driven by robot too)
	var widgetsSpawned = false;
	
	function createStandardWidgets() {
		// Show and hide the right buttons
		$("#debugsplash").hide();

		$("#wizard-tray").hide();
		$("#widget-tray").show();

		$("#corner-button").show();

		// Create widgets in the tray (the list may vary)

		if (!widgetsSpawned) {
			insertTrayWidget("traywidgets/language/language.html", "available");
			// The following are deliberately in the wrong order, so they can be sorted
			insertTrayWidget("traywidgets/store/store.html");
			insertTrayWidget("traywidgets/orientation/orientation.html", "available", "unavailable");
			insertTrayWidget("traywidgets/network/network.html");

			// ALife has been diisactivated in favour of the top right exit button
			//insertTrayWidget("traywidgets/alife/alife.html");

			// TODO: get state from QiMessaging
			// (for standalone version, a fake timeout is used)
			setTimeout(function(){
				//setTrayWidgetState("language", "available", "French"); 
				setTrayWidgetState("network", "available", "connected"); 
				//setTrayWidgetState("store", "unavailable", "unavailable"); 
				setTrayWidgetState("store", "available", "needed"); 
				//setTrayWidgetState("alife", "available", "unavailable"); 
				//setTrayWidgetState("orientation", "available", "unavailable"); 
			}, 1000);
			widgetsSpawned = true;
		}
	};
	
	// Wizard system

	function loadWizardFragment(fragment) {
		$("#wizard-backbutton").toggle(g_posInWizard > 0);
		// This may need a better handling of skip/next distinction
		// (right now it tends to be over
		if (g_posInWizard >= g_wizardFragments.length - 1) {
			$("#wizard-nextbutton").html("FINISH!");
		} else {
			$("#wizard-nextbutton").html("Next");
		}
		$("#wizard-nextbutton").addClass("disabled");
		// This may trigger override of button labels
		loadFragment(fragment);

		
	}

	function setWizardPos(pos) {
		g_posInWizard = pos;
		loadWizardFragment(g_wizardFragments[g_posInWizard]);
		if ($.raiseALMemoryEvent) {
			$.raiseALMemoryEvent("BootConfig/pageChanged", g_wizardNames[g_posInWizard]);
		}
	}

	$("#wizard-backbutton").mousedown(function() {
		customfragment = $(this).data("customfragment");
		if (customfragment) {
			$(this).removeData("customfragment");
			loadWizardFragment(customfragment);
		} else if (g_posInWizard > 0) {
			setWizardPos(g_posInWizard - 1);
		}
		// else, shouldn't happen
	});
	
	$("#wizard-nextbutton").mousedown(function() {
		if (!$(this).hasClass("disabled")) {
			var next = g_posInWizard + 1;
			if (next < g_wizardFragments.length) {
				setWizardPos(next);
			} else {
				createStandardWidgets(); // Also closes wizard, etc.
				loadFragment("");
				$("#corner-button").hide();
				$("#corner-unfolded-button").show();
				$.raiseALMemoryEvent("BootConfig/wizardDone", "wizardDone");
				event.stopPropagation();
			}
		}
	});
	
	
	function createWizard() {
		$("#debugsplash").hide();

		$("#widget-tray").hide();
		$("#wizard-tray").show();
		
		$("#corner-button").hide();
		
		// Setup page list, and launch
		// This information is redundant, we might want to retrieve it from widgets instead
		g_wizardNames =     ["language",
							 null,
							 "network",
							 "store",
							 ];
		g_wizardFragments = ["fragments/language/language.html",
							 "fragments/eula/eula.html",
							 "fragments/network/network_manual.html",
							 "fragments/store/store.html",
							 ];
		setWizardPos(0);
	}
	
	$("#makefakewidgets").mousedown(function(event) {
		createStandardWidgets();
		$("#corner-button").hide();
		$("#corner-unfolded-button").show();
		$.unselectAllWidgets();
		event.stopPropagation();
	});
	$("#launchwizard").mousedown(createWizard);

	if ($.recvData) {
		log("[DBG] Waiting gor state");
		$.recvData("BootConfig/showState", function(wantedState) {
			log("[DBG] received BootConfig/showState: " + wantedState);
			if (wantedState == "wizard") {
				createWizard();
			}
			else if (wantedState == "menu") {
				createStandardWidgets();
			} else {
				log("Unexpected argument to BootConfig/showState: " + wantedState);
			}
		});
		
		$.recvData("BootConfig/setStatusText", function(statusText){
			$("#status").html(statusText);
		});
		
		$.recvData("BootConfig/addWidget", function(params){
			var widgetUrl = params[0];
			var buttonState = params[1];
			var iconState = params[2];
			log("[JSON] Received: " + widgetUrl + " and arg: " + buttonState + " and " + iconState);
			insertTrayWidget(widgetUrl, buttonState, iconState);
		});
		
		// These are test buttons, for investigating some json bugs
		$("#dbgsendjson").mousedown(function() {
			var json = {"event": "BootConfig/showState", "value": ["wizard"]};
			$.sendData("JSONSERVER-OUT", json);
		});
		$("#dbgsendsubscribe").mousedown(function() {
			$.sendData("TestSubscribe", "CheckIfSubscribed.");
		});
	}
	
	// This allows us to preserve the same fragment if we keep the page in browser
	if (window.location.hash) {
		createStandardWidgets();
		loadFragment(window.location.hash.slice(1));
	}
	
	if (isOnRobot()) {
		$("#debugsplash").hide();
	}
});