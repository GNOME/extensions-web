export default class TestExtension {
    enable() {
        this._items = new Map();
    }

    disable() {
        this._items = null;
    }
}
