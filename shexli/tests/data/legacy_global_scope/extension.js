const { GObject } = imports.gi;

var KeyManager = GObject.registerClass(
    class KeyManager extends GObject.Object {
        _init() {
            super._init();
            global.display.connect("accelerator-activated", () => {});
        }
    }
);

let keyManager = new KeyManager();

class Extension {
    enable() {}
    disable() {}
}

function init() {
    return new Extension();
}
