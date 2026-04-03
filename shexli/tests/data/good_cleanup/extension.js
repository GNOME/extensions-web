import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

export default class GoodCleanup extends Extension {
    enable() {
        const id = global.settings.connect('changed::favorite-apps', () => {});
        this._signalIds.push(id);
        this._sourceIds.push(GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 5, () => GLib.SOURCE_CONTINUE));
        this._actors.push(new St.BoxLayout());
        this._setupMore();
    }

    _setupMore() {
        this._signalIds.push(Main.panel.connect('notify::visible', () => {}));
    }

    disable() {
        // unlock-dialog cleanup note
        this._cleanupResources();
    }

    _cleanupResources() {
        this._signalIds.forEach(id => global.settings.disconnect(id));
        for (const id of this._sourceIds)
            GLib.Source.remove(id);
        for (const actor of this._actors)
            actor.destroy();
    }
}

