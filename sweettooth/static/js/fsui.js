/*
    GNOME Shell extensions repository
    Copyright (C) 2012  Jasper St. Pierre <jstpierre@mecheye.net>
    Copyright (C) 2017  Yuri Konotopov <ykonotopov@gnome.org>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
 */

// FSUI is short for "Filtering and Sorting UI", which contains
// controls for filtering and sorting the extensions list

define(['jquery', 'dbus!_', 'hashParamUtils', 'modal'],
	function ($, dbusProxy, hashParamUtils, modal) {
		"use strict";

		function makeDropdownLink(text) {
			return $('<a>', {'class': 'fsui-dropdown-link'}).append($('<span>').text(text)).append($('<span>', {'class': 'fsui-dropdown-link-arrow'}).text('\u2304'));
		}

		function makeDropdown($fsui, $link) {
			return $('<div>', {'class': 'fsui-dropdown'}).appendTo($fsui).css('right', calculateRight($fsui, $link)).hide().fadeIn('fast');
		}

		function calculateRight($fsui, $link) {
			return $fsui.innerWidth() - $link.position().left - $link.outerWidth() - parseFloat($link.css('marginLeft'));
		}

		function makeLink(key, value, text, closeUI) {
			return $('<li>', {'class': 'fsui-dropdown-item'}).text(text).click(function () {
				hashParamUtils.setHashParam(key, value);
				hashParamUtils.setHashParam('page', undefined);
				closeUI();
			});
		}

		var sortCriteria = {
			'name': gettext("Name"),
			'created': gettext("Recent"),
			'downloads': gettext("Downloads"),
			'popularity': gettext("Popularity"),
			'relevance': gettext("Relevance"),
		};

		$.fn.fsUIify = function () {

			return this.each(function () {
				var $elem = $(this);

				function makeCloseUI($link, $dropdown) {
					return function () {
						if ($link.hasClass('selected'))
						{
							$dropdown.fadeOut('fast', function () {
								$(this).detach();
							});
							$link.removeClass('selected');
							return true;
						}
						return false;
					};
				}

				var hp = hashParamUtils.getHashParams();
				if (hp.sort === undefined || !sortCriteria.hasOwnProperty(hp.sort))
				{
					hp.sort = 'popularity';
				}

				var $fsui = $('<div>', {'class': 'fsui'}).appendTo($elem);

				$fsui.append('<span>' + gettext('Sort by') + '</span>');

				var $link;

				$link = makeDropdownLink(sortCriteria[hp.sort]).click(function () {
					var $dropdown = makeDropdown($fsui, $(this));
					$(this).addClass('selected');
					var closeUI = makeCloseUI($(this), $dropdown);
					modal.activateModal($dropdown, closeUI);

					var $sortUL = $('<ul>').appendTo($dropdown);
					var sortLinks = {};
					$.each(sortCriteria, function (key) {
						sortLinks[key] = makeLink('sort', key, this, closeUI).appendTo($sortUL);
					});

					sortLinks[hp.sort].addClass('selected');

					return false;
				}).appendTo($fsui);

				function textForFilterValue(value) {
					if (value === 'all')
					{
						return "All versions";
					}
					else if (value === dbusProxy.ShellVersion)
					{
						return "Current version";
					}
					return "GNOME Shell version " + value;
				}

				if (dbusProxy.ShellVersion === undefined)
				{
					return;
				}

				var shellVersion = hp.shell_version;
				if (shellVersion === undefined)
				{
					if (dbusProxy.VersionValidationEnabled)
					{
						shellVersion = dbusProxy.ShellVersion;
					}
					else
					{
						shellVersion = 'all';
					}
				}

				$fsui.append('<span>' + gettext('Compatible with') + '</span>');

				$link = makeDropdownLink(textForFilterValue(shellVersion)).click(function () {
					var $dropdown = makeDropdown($fsui, $(this));
					$(this).addClass('selected');
					var closeUI = makeCloseUI($(this), $dropdown);
					modal.activateModal($dropdown, closeUI);

					var $filterUL = $('<ul>').appendTo($dropdown);

					$.each(['all', dbusProxy.ShellVersion], function () {
						var $filterItem = makeLink('shell_version', this, textForFilterValue(this), closeUI).appendTo($filterUL);
						if (shellVersion === this)
						{
							$filterItem.addClass('selected');
						}
					});

					return false;
				}).appendTo($fsui);
			});
		};
	});
