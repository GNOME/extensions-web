import Gtk from 'gi://Gtk';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

let settings = new Gio.Settings({schema_id: 'org.example.bad'});

export default class BadExtension extends Extension {
    enable() {
        this._id = global.settings.connect('changed::favorite-apps', () => {
            console.log('changed');
        });
        this._sourceId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 5, () => {
            console.log('tick');
            return GLib.SOURCE_CONTINUE;
        });
    }

    disable() {
        console.log('disabled');
    }
}

