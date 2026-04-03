const { getCurrentExtension } = imports.misc.extensionUtils;
const Helper = getCurrentExtension().imports.Helper;

function init() {
    return new Helper.Extension();
}
