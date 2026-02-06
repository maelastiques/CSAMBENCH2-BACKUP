var getQuery = function(key){
	var queryStr = document.documentURI.split("?")[1];

	if(queryStr == undefined){
		return null;
	}

	var queryArray = queryStr.split("&");

	for(var i = 0; i < queryArray.length; i++){
		data  = queryArray[i].split("=");
		if(data[0] === key){
			return data[1];
		}
	}
	return null;
}	

function zeroFill(number, width) {
  width -= number.toString().length;
  if (width > 0) {
    return new Array(width + 1).join('0') + number;
  }
  return "" + number;
}

function log(txt) {
	if (console) {
		console.log("" + txt);
	}
}

function isOnRobot() {
	// TODO: make this work in a more general way (enough for local testing)
	var hostname = window.location.hostname;
	return    (hostname != "localhost") 
	       && (hostname != "ald-1084-de.aldebaran.lan") // Emile's machine.
	       && (hostname != "10.0.253.77"); // Emile's machine also.
}
