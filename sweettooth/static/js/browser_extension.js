/*
    GNOME Shell extensions repository
    Copyright (C) 2017  Yuri Konotopov <ykonotopov@gnome.org>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
 */

IS_CHROME	= (typeof(chrome) !== 'undefined' && typeof(chrome.webstore) !== 'undefined');
IS_FIREFOX	= (typeof(InstallTrigger) !== 'undefined');
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
		// https://developer.mozilla.org/en-US/docs/Web/API/InstallTrigger/install
		InstallTrigger.install({
			'GNOME Shell integration': {
				'URL':  'https://addons.mozilla.org/firefox/downloads/latest/gnome-shell-integration/platform:2/addon-751081-latest.xpi'
			}
		}, function(url, status) {
			if (status == 0) {
				reload_page();
			}
		});
	}
	else if (IS_CHROME)
	{
		chrome.webstore.install(
			undefined,
			reload_page
		);
	}

	return false;
}
