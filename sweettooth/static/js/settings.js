/*
    GNOME Shell extensions repository
    Copyright (C) 2019  Yuri Konotopov <ykonotopov@gnome.org>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
 */

define(['jquery', 'dbus!_', 'template!extensions/settings'], function ($, dbusProxy, settingsTemplate) {
		"use strict";
		const SETTINGS = [
			{
				id: 'disable-user-extensions',
				name: 'Disable all extensions',
				description: 'Disable all extensions regardless per-extension enable setting.',
				enabled: () => {
					return typeof(dbusProxy.UserExtensionsDisabled) !== 'undefined';
				},
				get: () => {
					if(dbusProxy.IsDummy)
					{
						return;
					}

					return dbusProxy.GetUserExtensionsDisabled();
				},
				change: (value) => {
					return dbusProxy.SetUserExtensionsDisabled(value);
				}
			},
			{
				id: 'disable-extension-version-validation',
				name: 'Disable version validation',
				description: 'Allow to load extensions that do not claims to support running Shell version. Default to enabled for recent Shell versions.',
				enabled: () => {
					return dbusProxy.CanSetVersionValidationDisabled;
				},
				get: () => {
					if(dbusProxy.IsDummy)
					{
						return;
					}

					return dbusProxy.GetVersionValidationDisabled();
				},
				change: (value) => {
					return dbusProxy.SetVersionValidationDisabled(value);
				}
			}
		];

		function refreshExtensionsDisableState() {
			$('#local_extensions').find('.switch').switchify(dbusProxy.GetUserExtensionsDisabled() ? 'disable' : 'enable');
		}

		dbusProxy.shellSettingChangedHandler = (key, value) => {
			if(key === 'disable-user-extensions')
			{
				refreshExtensionsDisableState();
			}

			$('#setting-' + key)
				.data('value', value)
				.trigger('setting-changed');
		};

		$.fn.addShellSettings = function() {
			this.each(function() {
				let $container = $(this);

				for(let setting of SETTINGS)
				{
					let $elem = $(settingsTemplate.render(setting))
					$elem.data('value', setting.get());
					$container.append($elem)

					let $switch = $container.find('.switch');
					$switch.switchify('disable');

					$switch.on('changed', function (event, newValue) {
						if(newValue == $elem.data('value'))
						{
							return;
						}

						setting.change(newValue).then((status) => {
							if(!status)
							{
								console.log(`Unable to set value of ${setting.id}`);
							}
							else
							{
								$elem.data('value', newValue);
							}
						});
					});

					$elem.on('setting-changed', function(event) {
						if(setting.enabled())
						{
							$switch.switchify('enable');
							$switch.switchify('activate', setting.get());
						}
						else
						{
							$switch.switchify('disable');
						}
					});

					$elem.trigger('setting-changed');
				}
			});
		}
	}
);
