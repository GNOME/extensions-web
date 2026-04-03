import {DoNotDisturbSwitch} from 'resource:///org/gnome/shell/ui/calendar.js';

export default class Gnome49Break {
    enable() {
        this._clickAction = new Clutter.ClickAction();
        this._window.maximize(Meta.MaximizeFlags.BOTH);
        this._window.get_maximized();
        global.backend.get_cursor_tracker().set_pointer_visible(false);
        this._switch = DoNotDisturbSwitch;
    }

    disable() {
        this._clickAction = null;
    }
}
