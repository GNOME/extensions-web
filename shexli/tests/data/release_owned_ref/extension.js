export default class ExampleExtension {
    enable() {
        this._proxy = Gio.DBusProxy.new_sync(
            dbus,
            Gio.DBusProxyFlags.GET_INVALIDATED_PROPERTIES,
            null,
            "org.example.Service",
            "/org/example/Service",
            "org.example.Service",
            null,
        );
        this._signal = this._proxy.connect("g-signal", () => {});
    }

    disable() {
        this._proxy.disconnect(this._signal);
        this._signal = null;
    }
}
