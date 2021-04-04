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
	// See: https://gitlab.gnome.org/GNOME/gnome-shell/blob/master/js/ui/extensionSystem.js

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

	// https://gitlab.gnome.org/GNOME/gnome-shell/blob/master/js/misc/extensionUtils.js
	exports.ExtensionType = {
		SYSTEM: 1,
		PER_USER: 2
	};

	let prerelease_versions = {
		'alpha': -4,
		'beta': -3,
		'rc': -2,
	};

	function versionCompare(a, b) {
		function toInt(value) {
			if(value in Object.keys(prerelease_versions)) {
				return prerelease_versions[value];
			}

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

	exports.shellVersionCompare = versionCompare;

	exports.grabProperExtensionVersion = function (map, current, findBestVersion) {
		function getBestShellVersion() {
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

		var parts = current.split('.');
		// Don't use destruction assigment for now
		// We need new Vue frontend with babel....
		let major = parts[0];
		let minor = parts[1];
		let point = parts[2];

		let mappedVersion = null;
		if (major >= 40)
		{
			// alpha/beta/rc
			if(isNaN(parseInt(minor)))
				mappedVersion = map[major] || map[`${major}.${minor}`];
			else
				mappedVersion = map[`${major}.${minor}`] || map[major];
		}
		else
		{
			mappedVersion = map[`${major}.${minor}.${point}`];
			if (minor % 2 === 0 && !mappedVersion)
			{
				mappedVersion = map[`${major}.${minor}`];
			}
		}

		if(mappedVersion) {
			return mappedVersion;
		}

		if(findBestVersion)
		{
			return map[getBestShellVersion()];
		}

		return null;
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
