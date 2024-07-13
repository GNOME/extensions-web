/*
    GNOME Shell extensions repository
    Copyright (C) 2017  Yuri Konotopov <ykonotopov@gnome.org>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
 */

IS_CHROME	= (typeof(chrome) !== 'undefined' && (
	typeof(chrome.webstore) !== 'undefined' ||
	typeof(chrome.runtime) !== 'undefined' ||
	typeof(chrome.csi) !== 'undefined'
));
IS_FIREFOX	= CSS.supports("-moz-appearance: none");

function browser_extension_install() {
	function reload_page() {
		location.reload();
	}

	if(IS_FIREFOX)
	{
        let url = "https://addons.mozilla.org/firefox/downloads/latest/gnome-shell-integration/platform:2/addon-751081-latest.xpi";

        try {
            const version = parseFloat(navigator.userAgent.split(" ").pop().split("/").pop());
            if(version < 126) {
                url = "https://addons.mozilla.org/firefox/downloads/file/3974897/gnome_shell_integration-11.1.xpi";
            }
        }
        catch (e) { }

        window.location.assign(url);
	}
	else if (IS_CHROME)
	{
		window.open('https://chrome.google.com/webstore/detail/gphhapmejobijbbhgpjhcjognlahblep');
	}

	return false;
}
