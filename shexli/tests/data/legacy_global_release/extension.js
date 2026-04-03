let buttons;

class Configurator {
    _createMenu() {
        buttons = [];
    }

    enable() {
        this._createMenu();
    }

    disable() {
    }
}

function init() {
    return new Configurator();
}
