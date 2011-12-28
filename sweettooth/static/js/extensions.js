"use strict";

define(['jquery', 'messages', 'dbus!_', 'extensionUtils', 'paginator',
        'switch', 'jquery.tipsy'],
function($, messages, dbusProxy, extensionUtils) {

    var ExtensionState = extensionUtils.ExtensionState;

    $.fn.buildShellVersionsInfo = function () {
        return this.each(function() {
            var $table = $(this);
            var $tbody = $table.find('tbody');
            var $extension = $table.parents('.extension');
            var urlBase = $extension.data('ver-url-base');

            $tbody.children().remove();

            var svm = $extension.data('svm');
            for (var version in svm) {
                if (!svm.hasOwnProperty(version))
                    continue;

                var vpk = extensionUtils.grabProperExtensionVersion(svm, version);

                var $tr = $('<tr>').appendTo($tbody);

                $('<td>').append($('<code>').text(version)).appendTo($tr);
                $('<td>').append($('<a>', {'href': urlBase + vpk.pk}).text(vpk.version)).appendTo($tr);
            }
        });
    };

    // While technically we shouldn't have mismatched API versions,
    // the plugin doesn't check whether the Shell matches, so if someone
    // is running with an old Shell version but a newer plugin, error out.
    if (dbusProxy === undefined ||
        dbusProxy.ShellVersion === undefined) {
        // We don't have a proper DBus proxy -- it's probably an old
        // version of GNOME3 or the Shell.
        messages.addError("You do not appear to have an up to date version " +
                          "of GNOME3. You won't be able to install extensions " +
                          "from here. See the <a href=\"/about/#old-version\">about page</a> " +
                          "for more information");

        $.fn.addExtensionSwitch = function() {
            // Don't show our switches -- CSS styles define a clickable
            // area even with no content.
            $(this).find('.switch').hide();
        };

        $.fn.addLocalExtensions = function() {
            $(this).append("GNOME Shell Extensions cannot list your installed extensions.");
        };

        $.fn.fillInErrors = function() {
            var $form = $(this);
            var $textarea = $form.find('textarea[name=error]');
            var $hidden = $form.find('input:hidden[name=has_errors]');
            $textarea.text("GNOME Shell Extensions cannot automatically detect any errors.").
                addClass('no-errors').attr('disabled', 'disabled');
            $hidden.val('');
        };

        $.fn.addOutOfDateIndicator = function() {
        };

        $.fn.checkForUpdates = function() {
        };

        return;
    }

    // uuid => elem
    var elems = {};

    dbusProxy.extensionStateChangedHandler = function(uuid, newState, _) {
        if (elems[uuid] !== undefined)
            elems[uuid].trigger('state-changed', newState);
    };

    dbusProxy.shellRestartHandler = function() {
        dbusProxy.ListExtensions().done(function(extensions) {
            $.each(extensions, function(meta) {
                if (elems[uuid] !== undefined)
                    elems[uuid].trigger('state-changed', meta.state);
            });
        });
    };

    function addExtensionSwitch(uuid, extension, $elem) {
        var $switch = $elem.find('.switch');
        var _state = ExtensionState.UNINSTALLED;
        var svm = $elem.data('svm');

        var vpk = extensionUtils.grabProperExtensionVersion(svm, dbusProxy.ShellVersion);

        if (vpk === null) {
            if (svm) {
                _state = ExtensionState.OUT_OF_DATE;
            } else {
                // Allow the local extensions code to work without an svm.
                _state = extension.state;
            }
        } else if (extension && !$.isEmptyObject(extension)) {
            _state = extension.state;
        }

        $elem.data({'elem': $elem,
                    'pk': (vpk === null ? 0 : vpk.pk),
                    'state': _state,
                    'uninstalled': false,
                    'undo-uninstall-message': null});

        $switch.data('elem', $elem);
        $switch.switchify();
        if ($switch.hasClass('insensitive'))
            return;

        function sendPopularity(action) {
            $.ajax({ url: '/ajax/adjust-popularity/',
                     data: { uuid: uuid,
                             action: action } });
        }

        $switch.bind('changed', function(e, newValue) {
            var oldState = $elem.data('state');
            if (newValue) {
                if (oldState == ExtensionState.UNINSTALLED) {
                    // If the extension is uninstalled and we
                    // flick the switch on, install.
                    dbusProxy.InstallExtension(uuid, $elem.data('pk').toString());
                    sendPopularity('enable');
                } else if (oldState == ExtensionState.DISABLED ||
                           oldState == ExtensionState.INITIALIZED) {
                    dbusProxy.EnableExtension(uuid);
                    sendPopularity('enable');
                }
            } else {
                if (oldState == ExtensionState.ENABLED) {
                    dbusProxy.DisableExtension(uuid);
                    sendPopularity('disable');
                }
            }
        });

        $elem.bind('state-changed', function(e, newState) {
            $elem.data('state', newState);
            $switch.switchify('insensitive', false);
            $switch.tipsy({ gravity: 'w', fade: true });
            if (newState == ExtensionState.DISABLED ||
                newState == ExtensionState.INITIALIZED ||
                newState == ExtensionState.UNINSTALLED) {
                $switch.switchify('activate', false);
            } else if (newState == ExtensionState.ENABLED) {
                $switch.switchify('activate', true);
            } else if (newState == ExtensionState.ERROR) {
                $switch.switchify('insensitive', true);
                $switch.attr('title', "This extension had an error.");
            } else if (newState == ExtensionState.OUT_OF_DATE) {
                $switch.switchify('insensitive', true);
                $elem.trigger('out-of-date');
            }

            if ($elem.data('uninstalled') && (newState == ExtensionState.ENABLED ||
                                              newState == ExtensionState.ERROR ||
                                              newState == ExtensionState.OUT_OF_DATE)) {
                $elem.fadeIn({ queue: false }).slideDown();
                $elem.data('uninstalled', false);
                $elem.data('undo-uninstall-message').slideUp();
            }

        });
        $elem.trigger('state-changed', _state);
        elems[uuid] = $elem;
    }

    $.fn.addLocalExtensions = function () {
        return this.each(function() {
            var $container = $(this);
            dbusProxy.ListExtensions().done(function(extensions) {
                if (extensions && !$.isEmptyObject(extensions)) {
                    var extensionValues = [];
                    for (var uuid in extensions) {
                        extensionValues.push(extensions[uuid]);
                    }

                    extensionValues.sort(function(a, b) {
                        return a.name.localeCompare(b.name);
                    });

                    extensionValues.forEach(function(extension) {
                        var uuid = extension.uuid;

                        function reinstall() {
                            dbusProxy.InstallExtension(uuid, $elem.data('pk').toString());

                            // If the user clicks "Install" we need to show that we
                            // installed it by reattaching the element, but we can't do
                            // that here -- the user might click "Cancel".
                            $elem.data('uninstalled', true);
                        }

                        function uninstall() {
                            dbusProxy.UninstallExtension(uuid).done(function(result) {
                                if (result) {
                                    $elem.fadeOut({ queue: false }).slideUp({ queue: false });

                                    // Construct a dummy <p> node as we need something
                                    // to stuff everything else in...
                                    var messageHTML = $("<p>You uninstalled </p>").
                                        append($('<b>').text(extension.name)).
                                        append(". ").
                                        append($('<a>', {'href': '#'}).text("Undo?")).html();

                                    var $message = messages.addInfo(messageHTML);
                                    $message.delegate('a', 'click', reinstall);
                                    $elem.data('undo-uninstall-message', $message);
                                }
                            });
                        }

                        var $elem = $('<div>', {'class': 'extension'}).
                            append($('<div>', {'class': 'switch'})).
                            append($('<img>', {'class': 'icon'})).
                            append($('<h3>', {'class': 'extension-name'}).text(extension.name)).
                            append($('<span>', {'class': 'author'})).
                            append($('<p>', {'class': 'description'}).text(extension.description));

                        $.ajax({
                            url: "/ajax/detail/",
                            dataType: "json",
                            data: { uuid: extension.uuid,
                                    version: extension.version },
                            type: "GET",
                        }).done(function(result) {
                            $elem.
                                find('span.author').text(" by ").append($('<a>', {'href': "/accounts/profile/" + result.creator}).text(result.creator)).end().
                                find('img.icon').detach().end().
                                find('h3').html($('<a>', {'href': result.link}).append($('<img>', {'class': 'icon', 'src': result.icon})).append(extension.name)).end();

                            // The PK might not exist if the extension wasn't
                            // installed from GNOME Shell Extensions.
                            if (result.pk !== undefined) {
                                $elem.
                                    data('pk', result.pk).
                                    data('svm', $.parseJSON(result.shell_version_map)).
                                    append($('<button>', {'class': 'uninstall', 'title': "Uninstall"}).text("Uninstall").bind('click', uninstall)).
                                    addOutOfDateIndicator();
                            }

                            addExtensionSwitch(uuid, extension, $elem);
                        }).fail(function(e) {
                            // If the extension doesn't exist, add a switch anyway
                            // so the user can toggle the enabled state.
                            if (e.status == 404)
                                addExtensionSwitch(uuid, extension, $elem);
                        });

                        $container.append($elem);
                    });
                } else {
                    $container.append("You don't have any extensions installed.");
                }
            })
        });
    };

    $.fn.fillInErrors = function () {
        return this.each(function() {
            var $form = $(this);
            var uuid = $form.data('uuid');
            var $textarea = $form.find('textarea');
            dbusProxy.GetExtensionInfo(uuid).done(function(meta) {
                dbusProxy.GetErrors($form.data('uuid')).done(function(errors) {
                    var errorString;

                    var versionInformation = "";
                    versionInformation += "    Shell version: " + dbusProxy.ShellVersion + "\n";
                    versionInformation += "    Extension version: ";
                    if (meta && meta.version) {
                        versionInformation += meta.version;
                    } else {
                        versionInformation += "Not found";
                    }

                    if (errors && errors.length) {
                        errorString = errors.join('\n\n================\n\n');
                    } else {
                        errorString = "GNOME Shell Extensions did not detect any errors with this extension.";
                    }

                    var template = ("What's wrong?\n\n\n\n" +
                                    "What have you tried?\n\n\n\n" +
                                    "Automatically detected errors:\n\n" + errorString +
                                    "\n\nVersion information:\n\n" + versionInformation);

                    $textarea.text(template);
                });
            });
        });
    };

    $.fn.addExtensionSwitch = function () {
        return this.each(function() {
            var $extension = $(this);
            var uuid = $extension.data('uuid');

            $extension.bind('out-of-date', function() {
                var svm = $extension.data('svm');
                var nhvOperation = extensionUtils.findNextHighestVersion(svm, dbusProxy.ShellVersion);
                if (nhvOperation.operation === 'upgrade' &&
                    nhvOperation.stability === 'stable') {
                    messages.addError("This extension is incompatible with your version of GNOME. Please upgrade to GNOME " + nhvOperation.version);
                } else if (nhvOperation.operation === 'upgrade' &&
                           nhvOperation.stability === 'unstable') {
                    messages.addError("This extension is incompatible with your version of GNOME. This extension supports the GNOME unstable release, " + nhvOperation.version);
                } else if (nhvOperation.operation === 'downgrade') {
                    messages.addError("This extension is incompatible with your version of GNOME.");
                }
            });

            dbusProxy.GetExtensionInfo(uuid).done(function(meta) {
                addExtensionSwitch(uuid, meta, $extension);
            });
        });
    };

    $.fn.addOutOfDateIndicator = function() {
        return this.each(function() {
            var svm = $(this).data('svm');
            if (!svm)
                return;

            var vpk = extensionUtils.grabProperExtensionVersion(svm, dbusProxy.ShellVersion);
            if (vpk === null) {
                $(this).
                    addClass('out-of-date').
                    attr('title', "This extension is incompatible with your version of GNOME").
                    tipsy({ gravity: 'c', fade: true });
            }
        });
    };

    $.fn.checkForUpdates = function() {
        return this.each(function() {
            var $elem = $(this);
            var svm = $elem.data('svm');
            var uuid = $elem.data('uuid');
            if (!svm)
                return;

            var vpk = extensionUtils.grabProperExtensionVersion(svm, dbusProxy.ShellVersion);

            if (vpk === null)
                return;

            function upgrade() {
                dbusProxy.UninstallExtension(uuid).done(function() {
                    dbusProxy.InstallExtension(uuid, vpk.version.toString());
                });
            }

            dbusProxy.GetExtensionInfo(uuid).done(function(meta) {
                var extensionName = $elem.find('.extension-name').text();
                var $upgradeMe = $elem.find('.upgrade-me');
                if (!meta)
                    return;

                if (vpk.version > meta.version) {
                    var msg = "You have version " + meta.version + " of";
                    msg += "\"" + extensionName + "\"";
                    msg += ". The latest version is version " + vpk.version;
                    msg += ". Click here to upgrade.";

                    $upgradeMe.append($('<a>', { href: '#' }).txt(msg).click(upgrade));
                } else if (vpk.version == meta.version) {
                    var msg = "You have the latest version of ";
                    msg += "\"" + extensionName + "\"";
                    $upgradeMe.text(msg);
                }
            });
        });
    };

});
