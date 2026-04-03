export default class TestExtension {
    enable() {
        this._sourceId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 1000, () => {
            return GLib.SOURCE_CONTINUE;
        });
    }

    disable() {
        if (this._sourceId) {
            GLib.source_remove(this._sourceId);
            this._sourceId = null;
        }
    }
}
