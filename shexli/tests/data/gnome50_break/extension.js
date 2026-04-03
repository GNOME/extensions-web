import * as RunDialog from 'resource:///org/gnome/shell/ui/runDialog.js';

export default class Gnome50Break {
    enable() {
        global.display.connect('restart', () => {});
        RunDialog._restart();
    }

    disable() {}
}

