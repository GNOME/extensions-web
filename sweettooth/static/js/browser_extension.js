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
IS_OPERA	= (typeof(opr) !== 'undefined');

function browser_extension_install() {
	function reload_page() {
		location.reload();
	}

	if (IS_OPERA)
	{
		opr.addons.installExtension(
			'olkooankbfblcebocnkjganpdmflbnbk',
			reload_page
		);
	}
	else if(IS_FIREFOX)
	{
		window.location.assign('https://addons.mozilla.org/firefox/downloads/latest/gnome-shell-integration/platform:2/addon-751081-latest.xpi');
	}
	else if (IS_CHROME)
	{
		window.open('https://chrome.google.com/webstore/detail/gphhapmejobijbbhgpjhcjognlahblep');
	}

	return false;
}
