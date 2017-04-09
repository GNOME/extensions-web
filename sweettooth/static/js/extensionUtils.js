/*
    GNOME Shell extensions repository
    Copyright (C) 2011-2012  Jasper St. Pierre <jstpierre@mecheye.net>
    Copyright (C) 2017  Yuri Konotopov <ykonotopov@gnome.org>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
 */

define([], function () {
	"use strict";

	var exports = {};

	// ExtensionState is stolen and should be kept in sync with the Shell.
	// Licensed under GPL2+
	// See: http://git.gnome.org/browse/gnome-shell/tree/js/ui/extensionSystem.js

	exports.ExtensionState = {
		ENABLED: 1,
		DISABLED: 2,
		ERROR: 3,
		OUT_OF_DATE: 4,
		DOWNLOADING: 5,
		INITIALIZED: 6,

		// Not a real state, used when there's no extension
		// with the associated UUID in the extension map.
		UNINSTALLED: 99
	};

	// https://git.gnome.org/browse/gnome-shell/tree/js/misc/extensionUtils.js
	exports.ExtensionType = {
		SYSTEM: 1,
		PER_USER: 2
	};

	exports.grabProperExtensionVersion = function (map, current, findBestVersion) {
		function getBestShellVersion() {
			function versionCompare(a, b) {
				function toInt(value) {
					return parseInt(value);
				}

				if (a == b)
				{
					return 0;
				}

				a = a.split('.').map(toInt);
				b = b.split('.').map(toInt);

				for (let i = 0; i < Math.max(a.length, b.length); i++)
				{
					if (a.length < i + 1)
					{
						return -1;
					}

					if (b.length < i + 1)
					{
						return 1;
					}

					if (a[i] < b[i])
					{
						return -1;
					}

					if (b[i] < a[i])
					{
						return 1;
					}
				}

				return 0;
			}

			let supported_shell_versions = Object.keys(map).sort(versionCompare);

			if (versionCompare(supported_shell_versions[0], current) == 1)
			{
				return supported_shell_versions[0];
			}
			else
			{
				return supported_shell_versions[supported_shell_versions.length - 1];
			}
		}


		if (!map || !current)
		{
			return null;
		}

		// Only care about the first three parts -- look up
		// "3.2.2" when given "3.2.2.1"

		var parts = current.split('.');

		var versionA = map[(parts[0] + '.' + parts[1] + '.' + parts[2])];

		// Unstable releases
		if (parseInt(parts[1]) % 2 != 0)
		{
			if (versionA !== undefined)
			{
				return versionA;
			}
			else if(findBestVersion)
			{
				return map[getBestShellVersion()];
			}
			else
			{
				return null;
			}
		}

		var versionB = map[(parts[0] + '.' + parts[1])];

		if (versionA !== undefined && versionB !== undefined)
		{
			return (versionA.version > versionB.version) ? versionA : versionB;
		}
		else if (versionA !== undefined)
		{
			return versionA;
		}
		else if (versionB !== undefined)
		{
			return versionB;
		}
		else if(findBestVersion)
		{
			return map[getBestShellVersion()];
		}
		else
		{
			return null;
		}
	};

	exports.findNextHighestVersion = function (map, current) {
		function saneParseInt(p) {
			return parseInt(p, 10);
		}

		var currentParts = current.split('.').map(saneParseInt);
		var nextHighestParts = [Infinity, Infinity, Infinity];

		$.each(map, function (key) {
			var parts = key.split('.').map(saneParseInt);

			if (parts[0] >= currentParts[0] &&
				parts[1] >= currentParts[1] &&
				((parts[2] !== undefined && parts[2] >= currentParts[2])
				|| parts[2] === undefined) &&
				parts[0] < nextHighestParts[0] &&
				parts[1] < nextHighestParts[1] &&
				((parts[2] !== undefined && parts[2] < nextHighestParts[2]) || parts[2] === undefined))
			{
				nextHighestParts = parts;
			}
		});

		// In this case, it's a downgrade.
		if (nextHighestParts[0] === Infinity ||
			nextHighestParts[1] === Infinity ||
			nextHighestParts[2] === Infinity)
		{
			return {'operation': 'downgrade'};
		}

		return {
			'operation': 'upgrade',
			'stability': (nextHighestParts[1] % 2 === 0) ? 'stable' : 'unstable',
			'version': nextHighestParts.join('.')
		};
	};

	return exports;

});
