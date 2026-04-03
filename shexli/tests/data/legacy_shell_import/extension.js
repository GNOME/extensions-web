const { Gtk, St } = imports.gi;

class Extension {
    enable() {}
    disable() {}
}

function init() {
    return new Extension();
}
