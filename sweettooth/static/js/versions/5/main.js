/*
    GNOME Shell extensions repository
    Copyright (C) 2012  Jasper St. Pierre <jstpierre@mecheye.net>
    Copyright (C) 2017-2019  Yuri Konotopov <ykonotopov@gnome.org>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
 */

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

        GetUserExtensionsDisabled: common.GetUserExtensionsDisabled,
        GetVersionValidationDisabled: common.GetVersionValidationDisabled,
        SetUserExtensionsDisabled: common.Reject,
        SetVersionValidationDisabled: common.Reject,

        CanSetVersionValidationDisabled: false,

        ShellVersion: API.shellVersion,
        VersionValidationEnabled: typeof(API.versionValidationEnabled) == 'undefined' || API.versionValidationEnabled,

        extensionStateChangedHandler: null,
        shellRestartHandler: null
    };

    API.onchange = common.API_onchange(proxy);
    API.onshellrestart = common.API_onshellrestart(proxy);

    return proxy;
});
