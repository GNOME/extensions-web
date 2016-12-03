// -*- mode: js; js-indent-level: 4; indent-tabs-mode: nil -*-

define(['jquery', 'dbus!API'], function($, API) {
    "use strict";

    function _makeRawPromise(result) {
        return (new $.Deferred()).resolve(result);
    }

    function _makePromise(result) {
        // Check if result is promise already
        if(isPromise(result))
        {
            return result;
        }

        return _makeRawPromise(JSON.parse(result));
    }

    function isPromise(value) {
        return value && typeof(value.then) == 'function';
    }

    return {
        _makePromise: _makePromise,

        ListExtensions: function() {
            return _makePromise(API.listExtensions());
        },

        GetExtensionInfo: function(uuid) {
            return _makePromise(API.getExtensionInfo(uuid));
        },

        GetErrors: function(uuid) {
            return _makePromise(API.getExtensionErrors(uuid));
        },

        LaunchExtensionPrefs: function(uuid) {
            return API.launchExtensionPrefs(uuid);
        },

        LaunchExtensionPrefsDummy: function(uuid) { },

        EnableExtension: function(uuid) {
            API.setExtensionEnabled(uuid, true);
        },

        DisableExtension: function(uuid) {
            API.setExtensionEnabled(uuid, false);
        },

        InstallExtensionOne: function(uuid) {
            var result = API.installExtension(uuid);

            if(isPromise(result))
                return result;

            return _makeRawPromise('succeeded');
        },

        InstallExtensionTwo: function(uuid) {
            var result = API.installExtension(uuid, "");

            if(isPromise(result))
                return result;

            return _makeRawPromise('succeeded');
        },

        InstallExtensionAsync: function(uuid) {
            var d = new $.Deferred();
            var result = API.installExtension(uuid, d.done.bind(d), d.fail.bind(d));

            if(isPromise(result))
                return result;

            return d;
        },

        UninstallExtension: function(uuid) {
            return _makePromise(API.uninstallExtension(uuid));
        },

        API_onchange: function(proxy) {
            return function(uuid, newState, error) {
                if (proxy.extensionStateChangedHandler !== null)
                    proxy.extensionStateChangedHandler(uuid, newState, error);
            };
        },

        API_onshellrestart: function(proxy) {
            return function() {
                if (proxy.shellRestartHandler !== null)
                    proxy.shellRestartHandler();
            };
        }
    };
});
