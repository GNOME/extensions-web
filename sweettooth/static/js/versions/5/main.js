// -*- mode: js; js-indent-level: 4; indent-tabs-mode: nil -*-

define(['jquery', 'dbus!API', 'versions/common/common'], function($, API, common) {
    "use strict";

    var proxy = {
        IsDummy: false,

        ListExtensions: common.ListExtensions,
        GetExtensionInfo: common.GetExtensionInfo,
        GetErrors: common.GetErrors,
        EnableExtension: common.EnableExtension,
        DisableExtension: common.DisableExtension,
        InstallExtension: common.InstallExtensionAsync,
        UninstallExtension: common.UninstallExtension,
        LaunchExtensionPrefs: common.LaunchExtensionPrefs,

        ShellVersion: API.shellVersion,
        VersionValidationEnabled: typeof(API.versionValidationEnabled) == 'undefined' || API.versionValidationEnabled,

        extensionStateChangedHandler: null,
        shellRestartHandler: null
    };

    API.onchange = common.API_onchange(proxy);
    API.onshellrestart = common.API_onshellrestart(proxy);

    return proxy;
});
