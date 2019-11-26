/*
    GNOME Shell extensions repository
    Copyright (C) 2011-2012  Jasper St. Pierre <jstpierre@mecheye.net>
    Copyright (C) 2016-2017  Yuri Konotopov <ykonotopov@gnome.org>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
 */

define(['jquery', 'dbus!API'], function ($, API) {
	"use strict";

	function _makeRawPromise(result) {
		return (new $.Deferred()).resolve(result);
	}

	function _makePromise(result, resolveValue) {
		// Check if result is promise already
		if (isPromise(result))
		{
			return result;
		}

		return _makeRawPromise(typeof(resolveValue) == 'undefined' ? JSON.parse(result) : resolveValue);
	}

	function isPromise(value) {
		return value && typeof(value.then) == 'function';
	}

	return {
		_makePromise: _makePromise,

		ListExtensions: function () {
			return _makePromise(API.listExtensions());
		},

		GetExtensionInfo: function (uuid) {
			return _makePromise(API.getExtensionInfo(uuid));
		},

		GetErrors: function (uuid) {
			return _makePromise(API.getExtensionErrors(uuid));
		},

		LaunchExtensionPrefs: function (uuid) {
			return API.launchExtensionPrefs(uuid);
		},

		LaunchExtensionPrefsDummy: function (uuid) {
		},

		EnableExtension: function (uuid) {
			return _makePromise(API.setExtensionEnabled(uuid, true), true);
		},

		DisableExtension: function (uuid) {
			return _makePromise(API.setExtensionEnabled(uuid, false), true);
		},

		InstallExtensionOne: function (uuid) {
			return _makePromise(API.installExtension(uuid), 'succeeded');
		},

		InstallExtensionTwo: function (uuid) {
			return _makePromise(API.installExtension(uuid, ""), 'succeeded');
		},

		InstallExtensionAsync: function (uuid) {
			var d = new $.Deferred();
			var result = API.installExtension(uuid, d.done.bind(d), d.fail.bind(d));

			if (isPromise(result))
			{
				return result;
			}

			return d;
		},

		UninstallExtension: function (uuid) {
			return _makePromise(API.uninstallExtension(uuid));
		},

		GetUserExtensionsDisabled: function(disabled) {
			return API.userExtensionsDisabled;
		},

		GetVersionValidationDisabled: function(disabled) {
			return !API.versionValidationEnabled;
		},

		SetUserExtensionsDisabled: function(disabled) {
			return API.setUserExtensionsDisabled(disabled);
		},

		SetVersionValidationDisabled: function(disabled) {
			return API.setVersionValidationDisabled(disabled);
		},

		Reject: function() {
			return Promise.reject();
		},

		API_onchange: function (proxy) {
			return function (uuid, newState, error) {
				if (proxy.extensionStateChangedHandler !== null)
				{
					proxy.extensionStateChangedHandler(uuid, newState, error);
				}
			};
		},

		API_onshellrestart: function (proxy) {
			return function () {
				if (proxy.shellRestartHandler !== null)
				{
					proxy.shellRestartHandler();
				}
			};
		},

		API_onShellSettingChanged: function (proxy) {
			return function (key, value) {
				if (proxy.shellSettingChangedHandler !== null)
				{
					proxy.shellSettingChangedHandler(key, value);
				}
			};
		}
	};
});
