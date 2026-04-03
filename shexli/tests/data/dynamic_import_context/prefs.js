export default class Preferences {
    async fillPreferencesWindow() {
        const helper = await import('./helper.js');
        return helper.loadWidget();
    }
}
