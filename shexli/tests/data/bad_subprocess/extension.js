import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

export default class BadSubprocess extends Extension {
    enable() {
        GLib.spawn_async(null, ['sudo', 'systemctl', 'restart', 'foo'], null, 0, null);
    }

    disable() {}
}

