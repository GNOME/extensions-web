import {DoNotDisturbSwitch} from 'resource:///org/gnome/shell/ui/calendar.js';
import * as RunDialog from 'resource:///org/gnome/shell/ui/runDialog.js';

export default class Gnome48Ok {
    enable() {
        this._clickAction = new Clutter.ClickAction();
        this._window.maximize(Meta.MaximizeFlags.BOTH);
        global.display.connect('restart', () => {});
        RunDialog._restart();
        this._switch = DoNotDisturbSwitch;
    }

    disable() {
        this._clickAction = null;
    }
}

