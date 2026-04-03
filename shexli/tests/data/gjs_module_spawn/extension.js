import Gio from "gi://Gio";

export default class TestExtension {
    enable() {
        Gio.Subprocess.new(
            ["gjs", "-m", `${this.path}/helper.js`],
            Gio.SubprocessFlags.NONE,
        );
    }
}
