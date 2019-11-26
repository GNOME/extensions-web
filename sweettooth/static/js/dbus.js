/*
    GNOME Shell extensions repository
    Copyright (C) 2011-2012  Jasper St. Pierre <jstpierre@mecheye.net>
    Copyright (C) 2016-2019  Yuri Konotopov <ykonotopov@gnome.org>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
 */

// We need to abuse the plugin system so that we can defer the
// load completion until our dynamically built requirement is
// loaded.

// Thanks to James Burke for helping me with this.
// http://groups.google.com/group/requirejs/msg/cc6016210c53a51d

define(['jquery'], function ($) {
	"use strict";

	const SUPPORTED_APIS = [5, 6];
	var exports = {};

	var load = exports.load = function (name, req, onLoad, config) {
		function processLoad() {
			if (name == "API")
			{
				onLoad(window.SweetTooth);
				return;
			}

			var apiVersion = undefined;

			try
			{
				if (window.SweetTooth)
				{
					apiVersion = window.SweetTooth.apiVersion;
				}
			}
			catch (e) { }

			if (!apiVersion || SUPPORTED_APIS.indexOf(apiVersion) === -1)
			{
				apiVersion = 'dummy';
			}

			var scriptname = './versions/' + apiVersion + '/main';
			// requirejs caches response.
			req([scriptname], function (module) {
				onLoad(module);
			});
		}

		$(document).ready(function () {
			if (!('SweetTooth' in window))
			{
				// Try NPAPI plugin
				try
				{
					var MIME_TYPE = 'application/x-gnome-shell-integration';
					var $plg = $('<embed>', {type: MIME_TYPE});

					// Netscape plugins are strange: if you make them invisible with
					// CSS or give them 0 width/height, they won't load. Just smack it
					// off-screen so it isn't visible, but still works.
					$plg.css({
						position: 'absolute',
						left: '-1000em',
						top: '-1000em'
					});

					// TODO: this may not work if the DOM is not ready
					// when this call is made. Depending on browsers
					// you want to support, either listen to
					// DOMContentLoaded, event, or use $(function(){}), but in
					// those cases, the full body of this load action should
					// be in that call.
					$(document.body).append($plg);

					// The API is defined on the plugin itself.
					window.SweetTooth = $plg[0];
				}
				catch (e)
				{
					// In this case we probably failed the origin checks and
					// the NPAPI plugin spat out an error. Explicitly set the
					// plugin to NULL
					window.SweetTooth = null;
				}

				processLoad();
			}
			else if (typeof(SweetTooth.initialize) === 'function')
			{
				// Browser extension
				// SweetTooth.initialize should be Promise or jQuery.Deferred
				SweetTooth.initialize().then(processLoad, processLoad);
			}
			else
			{
				processLoad();
			}
		});
	};

	return exports;
});
