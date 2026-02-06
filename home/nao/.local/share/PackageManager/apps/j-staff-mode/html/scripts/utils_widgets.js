function loadFragment(fragmentUrl, showEmptyTransition) {
    if (showEmptyTransition !== false) { // So we default to true
		$("#contents").html("");
	}
	var baseUrl = window.location.origin + window.location.pathname;
	if (fragmentUrl) {
		// there could be "loading..." or something.
		$("#contents").load(fragmentUrl);
		var newUrl = baseUrl + '#' + fragmentUrl;
		window.history.pushState("", newUrl, newUrl);
	} else {
		// Load no fragment: reset an url without hashtags, and an empty page
		window.history.pushState("", baseUrl, baseUrl);
	}
}

// lightweight jQuery plugin
(function( $ ) {

	function rankedInsert(container, element) {
		var rank = element.data("rank");
		var inserted = false;
		container.children().each(function(index, other) {
			var other_rank = $(other).data("rank");
			if (other_rank > rank) {
				element.insertBefore(other);
				inserted = true;
				return false;
			}
		});
		if (!inserted) {
			// Couldn't insert it in the list, just append it at the end.
			element.appendTo(container);
		}
	};
	
	// Debug function to help manually change widgets when in browser
	function DBG_cycleButtonState(widget) {
		if (widget.hasClass("unavailable")) {
			widget.setButtonState("available");
		} else {
			widget.setButtonState("unavailable");
		}
	}
	
	// Debug function to help manually change widgets when in browser
	function DBG_cycleIconState(widget) {
		var dataDic = widget.data();
		var states = [];
		var iconFiles = []
		$.each(dataDic, function(key, iconFile) {
			if (key.indexOf("icon_") === 0) {
				if (iconFiles.indexOf(iconFile) < 0) {
					var state = key.substring(5);
					states.push(state);
					iconFiles.push(iconFile);
				}
			}
		});
		if (states.length) {
			var stateIndex = 0;
			if (dataDic.DBGStateIndex !== undefined) {
				stateIndex = (1 + dataDic.DBGStateIndex) % states.length;
			}
			log("DBG: setting widget " + dataDic.name + " Icon to " + states[stateIndex]);
			widget.data("DBGStateIndex", stateIndex);
			widget.setIconState(states[stateIndex]);
		}
	}

	$.fn.registerWidget = function(icons){
		if (icons) {
			this.data("icons", icons);
		}
		var widget = this;
		// Place in visible zone
		if (widget.data("rank") < 0) {
			rankedInsert($("#right-widget-tray"), widget);
		} else {
			rankedInsert($("#widget-tray"), widget);
		}
		// Add button callback
		this.mousedown(function(event) {
			if (event.ctrlKey) {
				DBG_cycleButtonState(widget);
			}
			else if (event.shiftKey) {
				DBG_cycleIconState(widget);
			}
			if (widget.hasClass("available")) {
				// Update visual state
				widget.setButtonState("selected");
				// Send event back to robot (for now, we send it all the time. We might want to restrict that)
				$.raiseALMemoryEvent("BootConfig/pageChanged", widget.data("name"));
				loadFragment(widget.data("fragment"));
			}
			else if (widget.hasClass("selected")) {
				// Send the message anyway, but don't change case.
				$.raiseALMemoryEvent("BootConfig/pageChanged", widget.data("name"));
			}
		});
		return this;
	}

	// Sets the icon state and thus the icon itself.
	$.fn.setIconState = function(iconState){
		if (this.length) {
			var name = this.data("name");
			if (iconState) {
				var icon = this.data("icon_" + iconState.toLowerCase());
				if (icon) {
					// Note: here we force a width, because we're using temporary images.
					//log("[DBG] Widget " + name + ": setting icon " + icon);
					this.children(".icon").attr("width", "100px").attr("src", "traywidgets/" + name + "/" + icon);
				} else {
					log("[DBG] Widget " + name + ": no icon for iconState " + iconState);
					log("[DBG] Widget " + name + ": icons " + this.data("icons"));
				}
			} else {
				log("[DBG] Widget " + name + ": invalid iconState ");
			}
		}
	}
	
	var g_selected_widget = null;

	$.unselectAllWidgets = function() {
		if (g_selected_widget != null) {
			g_selected_widget.setButtonState("available");
		}
		g_selected_widget = null;
	}
	
	$.fn.setButtonState = function(state){
		//log("[DBG] Setting " + this.data("name") + " to buttonState: " + state);
		// Only one widget can be selected at a time - so unselect the previous one.
		if (this.length) {
			if (state === "selected"){
				$.unselectAllWidgets();
				g_selected_widget = this;
			}
			// State is stored as css class
			this.removeClass("available").removeClass("unavailable").removeClass("selected").addClass(state);
		}
	}
	

}( jQuery ));
	