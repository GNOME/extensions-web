# SPDX-License-Identifier: AGPL-3.0-or-later

import tempfile
import unittest
import zipfile
from pathlib import Path

from shexli import AnalysisLimits, analyze_path
from shexli.analyzer.evidence import node_evidence
from shexli.analyzer.lifecycle.cross_file import build_cross_file_indices_per_file
from shexli.analyzer.paths import PathMapper
from shexli.ast import iter_nodes, parse_js

DATA_DIR = Path(__file__).resolve().parent / "data"


class SmokeTest(unittest.TestCase):
    def _call_expression_snippet_containing(self, source: str, fragment: str) -> str:
        tree = parse_js(source)
        node = next(
            node
            for node in iter_nodes(tree.root_node)
            if node.type == "call_expression"
            and fragment in source[node.start_byte : node.end_byte]
        )
        mapper = PathMapper(Path("/tmp"), Path("/tmp"), "embedded", False)
        return node_evidence(Path("/tmp/extension.js"), source, node, mapper).snippet

    def test_bad_extension_reports_findings(self) -> None:
        result = analyze_path(DATA_DIR / "bad_extension")
        rule_ids = {finding.rule_id for finding in result.findings}
        self.assertIn("EGO-M-003", rule_ids)
        self.assertIn("EGO-M-004", rule_ids)
        self.assertIn("EGO-I-002", rule_ids)

    def test_multiline_node_snippet_preserves_space_indent(self) -> None:
        snippet = self._call_expression_snippet_containing(
            """
class E {
    enable() {
        this._settings.connect('changed::x', () => {
            this._update();
        });
    }
}
""".strip(),
            "this._settings.connect",
        )
        self.assertTrue(snippet.startswith("        this._settings.connect("))

    def test_multiline_node_snippet_preserves_tab_indent(self) -> None:
        snippet = self._call_expression_snippet_containing(
            (
                "class E {\n"
                "\tmethod() {\n"
                "\t\tthis._settings.connect('changed::x', () => {\n"
                "\t\t\tthis._update();\n"
                "\t\t});\n"
                "\t}\n"
                "}"
            ),
            "this._settings.connect",
        )
        self.assertTrue(snippet.startswith("\t\tthis._settings.connect("))

    def test_multiline_node_snippet_does_not_capture_prior_code_on_same_line(
        self,
    ) -> None:
        snippet = self._call_expression_snippet_containing(
            (
                "class E {\n"
                "    enable() {\n"
                "        console.log('x');        "
                "this._settings.connect('changed::x', () => {\n"
                "            this._update();\n"
                "        });\n"
                "    }\n"
                "}"
            ),
            "this._settings.connect",
        )
        self.assertTrue(snippet.startswith("this._settings.connect("))
        self.assertNotIn("console.log", snippet)

    def test_legacy_imports_gi_detect_shell_forbidden_imports(self) -> None:
        result = analyze_path(DATA_DIR / "legacy_shell_import")
        rule_ids = {finding.rule_id for finding in result.findings}
        self.assertIn("EGO-I-002", rule_ids)

    def test_good_cleanup_avoids_lifecycle_findings(self) -> None:
        result = analyze_path(DATA_DIR / "good_cleanup")
        rule_ids = {finding.rule_id for finding in result.findings}
        self.assertNotIn("EGO-L-002", rule_ids)
        self.assertNotIn("EGO-L-003", rule_ids)
        self.assertNotIn("EGO-L-004", rule_ids)

    def test_destroy_signal_bound_cleanup_suppresses_object_group_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"destroy-bound@example.com","name":"DestroyBound","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "extension.js").write_text(
                """
import GObject from "gi://GObject";
import St from "gi://St";
import * as SwitcherPopup from "resource:///org/gnome/shell/ui/switcherPopup.js";
import { Extension } from "resource:///org/gnome/shell/extensions/extension.js";

const Item = GObject.registerClass(
class Item extends St.BoxLayout {});

const Holder = GObject.registerClass(
class Holder extends SwitcherPopup.SwitcherList {
    _init() {
        super._init(false);
        this.items = [];
        const item = new Item();
        this.items.push(item);
        this.connect("destroy", this._onDestroy.bind(this));
    }

    _onDestroy() {
        for (const item of this.items) {
            item.destroy();
        }
        this.items = [];
    }
});

export default class E extends Extension {
    enable() {
        this._holder = new Holder();
    }

    disable() {
        this._holder.destroy();
        this._holder = null;
    }
}
""".strip(),
                encoding="utf-8",
            )

            result = analyze_path(root)
            rule_ids = {finding.rule_id for finding in result.findings}
            self.assertNotIn("EGO-L-002", rule_ids)

    def test_glib_source_remove_counts_as_cleanup(self) -> None:
        result = analyze_path(DATA_DIR / "source_remove_cleanup")
        rule_ids = {finding.rule_id for finding in result.findings}
        self.assertNotIn("EGO-L-004", rule_ids)

    def test_builtin_map_does_not_require_destroy(self) -> None:
        result = analyze_path(DATA_DIR / "builtin_map_cleanup")
        rule_ids = {finding.rule_id for finding in result.findings}
        self.assertNotIn("EGO-L-002", rule_ids)

    def test_bad_donations_are_rejected(self) -> None:
        result = analyze_path(DATA_DIR / "bad_donations")
        rule_ids = [finding.rule_id for finding in result.findings]
        self.assertIn("EGO-M-007", rule_ids)

    def test_bad_subprocess_is_flagged(self) -> None:
        result = analyze_path(DATA_DIR / "bad_subprocess")
        rule_ids = {finding.rule_id for finding in result.findings}
        self.assertIn("EGO-X-001", rule_ids)

    def test_privileged_subprocess_wrapper_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"wrapped-sudo@example.com","name":"WrappedSudo","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "extension.js").write_text(
                """
import Gio from "gi://Gio";
import { Extension } from "resource:///org/gnome/shell/extensions/extension.js";

function runProcess(argv) {
    return Gio.Subprocess.new(argv, Gio.SubprocessFlags.NONE);
}

export default class E extends Extension {
    enable() {
        runProcess(["sudo", "systemctl", "restart", "foo"]);
    }

    disable() {}
}
""".strip(),
                encoding="utf-8",
            )

            result = analyze_path(root)
            rule_ids = {finding.rule_id for finding in result.findings}
            self.assertIn("EGO-X-001", rule_ids)

    def test_privileged_runprocess_literal_argv_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"runprocess-sudo@example.com","name":"RunProcessSudo","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "extension.js").write_text(
                """
import { Extension } from "resource:///org/gnome/shell/extensions/extension.js";

function runProcess(argv) {
    return argv;
}

export default class E extends Extension {
    enable() {
        runProcess(["sudo", "systemctl", "restart", "foo"]);
    }

    disable() {}
}
""".strip(),
                encoding="utf-8",
            )

            result = analyze_path(root)
            rule_ids = {finding.rule_id for finding in result.findings}
            self.assertIn("EGO-X-001", rule_ids)

    def test_privileged_runprocess_with_dynamic_tail_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"runprocess-dynamic@example.com","name":"RunProcessDynamic","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "extension.js").write_text(
                """
import { Extension } from "resource:///org/gnome/shell/extensions/extension.js";

function runProcess(argv) {
    return argv;
}

export default class E extends Extension {
    enable() {
        const scriptPath = "/tmp/tool";
        runProcess(["sudo", scriptPath, "--help"]);
    }

    disable() {}
}
""".strip(),
                encoding="utf-8",
            )

            result = analyze_path(root)
            rule_ids = {finding.rule_id for finding in result.findings}
            self.assertIn("EGO-X-001", rule_ids)

    def test_sync_subprocess_in_shell_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"sync@example.com","name":"Sync","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "extension.js").write_text(
                (
                    "import GLib from 'gi://GLib';\n"
                    "export default class E {"
                    " enable() { GLib.spawn_command_line_sync('echo hi'); }"
                    " disable() {}"
                    " }"
                ),
                encoding="utf-8",
            )

            result = analyze_path(root)
            rule_ids = {finding.rule_id for finding in result.findings}
            self.assertIn("EGO-X-002", rule_ids)

    def test_run_dispose_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"dispose@example.com","name":"Dispose","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "extension.js").write_text(
                (
                    "export default class E {"
                    " enable() {}"
                    " disable() { this._obj.run_dispose(); }"
                    " }"
                ),
                encoding="utf-8",
            )

            result = analyze_path(root)
            rule_ids = {finding.rule_id for finding in result.findings}
            self.assertIn("EGO-X-003", rule_ids)

    def test_sync_file_io_in_shell_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"sync-io@example.com","name":"SyncIO","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "extension.js").write_text(
                (
                    "import Gio from 'gi://Gio';\n"
                    "export default class E {"
                    " enable() {"
                    "  const file = Gio.File.new_for_path('/proc/uptime');"
                    "  file.load_contents(null);"
                    " }"
                    " disable() {}"
                    " }"
                ),
                encoding="utf-8",
            )

            result = analyze_path(root)
            rule_ids = {finding.rule_id for finding in result.findings}
            self.assertIn("EGO-X-004", rule_ids)

    def test_imports_gi_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"imports-gi@example.com","name":"ImportsGi","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "extension.js").write_text(
                (
                    "const Gi = imports._gi;\n"
                    "export default class E { enable() {} disable() {} }"
                ),
                encoding="utf-8",
            )

            result = analyze_path(root)
            rule_ids = {finding.rule_id for finding in result.findings}
            self.assertIn("EGO-I-004", rule_ids)

    def test_get_preferences_widget_is_flagged_for_45_plus(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"prefs45@example.com","name":"Prefs45","description":"","shell-version":["45"]}',
                encoding="utf-8",
            )
            (root / "prefs.js").write_text(
                (
                    "function init() {}\n"
                    "function getPreferencesWidget() { return null; }\n"
                ),
                encoding="utf-8",
            )

            result = analyze_path(root)
            rule_ids = {finding.rule_id for finding in result.findings}
            self.assertIn("EGO-C45-001", rule_ids)

    def test_get_preferences_widget_is_not_flagged_before_45(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"prefs44@example.com","name":"Prefs44","description":"","shell-version":["44"]}',
                encoding="utf-8",
            )
            (root / "prefs.js").write_text(
                (
                    "function init() {}\n"
                    "function getPreferencesWidget() { return null; }\n"
                ),
                encoding="utf-8",
            )

            result = analyze_path(root)
            rule_ids = {finding.rule_id for finding in result.findings}
            self.assertNotIn("EGO-C45-001", rule_ids)

    def test_prefs_retained_instance_objects_require_close_request_cleanup(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"prefs-retain@example.com","name":"PrefsRetain","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "prefs.js").write_text(
                """
import Adw from "gi://Adw";
import { ExtensionPreferences } from "resource:///org/gnome/Shell/Extensions/js/extensions/prefs.js";

export default class Prefs extends ExtensionPreferences {
    #page;
    #settings;

    fillPreferencesWindow(window) {
        this.#settings = this.getSettings();
        this.#page = new Adw.PreferencesPage();
        window.add(this.#page);
    }
}
""".strip(),
                encoding="utf-8",
            )

            result = analyze_path(root)
            rule_ids = {finding.rule_id for finding in result.findings}
            self.assertIn("EGO-L-006", rule_ids)

    def test_prefs_close_request_cleanup_suppresses_retained_object_warning(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"prefs-close@example.com","name":"PrefsClose","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "prefs.js").write_text(
                """
import Adw from "gi://Adw";
import { ExtensionPreferences } from "resource:///org/gnome/Shell/Extensions/js/extensions/prefs.js";

export default class Prefs extends ExtensionPreferences {
    _page;

    fillPreferencesWindow(window) {
        this._page = new Adw.PreferencesPage();
        window.connect("close-request", () => {
            this._page = null;
        });
        window.add(this._page);
    }
}
""".strip(),
                encoding="utf-8",
            )

            result = analyze_path(root)
            rule_ids = {finding.rule_id for finding in result.findings}
            self.assertNotIn("EGO-L-006", rule_ids)

    def test_constructor_resource_ref_requires_release(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"ctor-ref@example.com","name":"CtorRef","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "extension.js").write_text(
                """
import Gio from "gi://Gio";
import { Extension } from "resource:///org/gnome/shell/extensions/extension.js";

export default class E extends Extension {
    constructor(metadata) {
        super(metadata);
        this._dbusImpl = Gio.DBusExportedObject.wrapJSObject("<node/>", this);
    }

    enable() {}

    disable() {
        this._dbusImpl.unexport();
    }
}
""".strip(),
                encoding="utf-8",
            )

            result = analyze_path(root)
            rule_ids = {finding.rule_id for finding in result.findings}
            self.assertIn("EGO-L-005", rule_ids)

    def test_constructor_custom_ref_requires_release_and_is_pre_enable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"ctor-custom@example.com","name":"CtorCustom","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "extension.js").write_text(
                """
import { InjectionManager, Extension } from "resource:///org/gnome/shell/extensions/extension.js";

export default class E extends Extension {
    constructor(metadata) {
        super(metadata);
        this._injectionManager = new InjectionManager();
    }

    enable() {}

    disable() {
        this._injectionManager.clear();
    }
}
""".strip(),
                encoding="utf-8",
            )

            result = analyze_path(root)
            rule_ids = {finding.rule_id for finding in result.findings}
            self.assertIn("EGO-L-001", rule_ids)
            self.assertIn("EGO-L-005", rule_ids)

    def test_entrypoint_factory_new_ref_requires_release(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"factory-ref@example.com","name":"FactoryRef","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "extension.js").write_text(
                """
import NM from "gi://NM";
import { Extension } from "resource:///org/gnome/shell/extensions/extension.js";

export default class E extends Extension {
    enable() {
        this._client = NM.Client.new(null);
    }

    disable() {}
}
""".strip(),
                encoding="utf-8",
            )

            result = analyze_path(root)
            rule_ids = {finding.rule_id for finding in result.findings}
            self.assertIn("EGO-L-005", rule_ids)

    def test_manual_default_stylesheet_loading_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"styleload@example.com","name":"StyleLoad","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "extension.js").write_text(
                """
import St from "gi://St";
import { Extension } from "resource:///org/gnome/shell/extensions/extension.js";

export default class E extends Extension {
    enable() {
        const theme = St.ThemeContext.get_for_stage(global.stage).get_theme();
        const cssFile = this.dir.get_child("stylesheet.css");
        theme.load_stylesheet(cssFile);
    }

    disable() {}
}
""".strip(),
                encoding="utf-8",
            )
            (root / "stylesheet.css").write_text("label {}", encoding="utf-8")

            result = analyze_path(root)
            rule_ids = {finding.rule_id for finding in result.findings}
            self.assertIn("EGO-X-005", rule_ids)

    def test_lookup_helpers_for_current_extension_are_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"lookup@example.com","name":"Lookup","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "prefs.js").write_text(
                """
import { ExtensionPreferences } from "resource:///org/gnome/Shell/Extensions/js/extensions/prefs.js";

export default class Prefs extends ExtensionPreferences {
    fillPreferencesWindow(window) {
        const settings = ExtensionPreferences
            .lookupByURL(import.meta.url)
            .getSettings();
        window._settings = settings;
    }
}
""".strip(),
                encoding="utf-8",
            )

            result = analyze_path(root)
            rule_ids = {finding.rule_id for finding in result.findings}
            self.assertIn("EGO-X-006", rule_ids)

    def test_missing_soup_session_abort_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"soup@example.com","name":"Soup","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "extension.js").write_text(
                """
import Soup from "gi://Soup";
import { Extension } from "resource:///org/gnome/shell/extensions/extension.js";

class Client {
    constructor() {
        this._session = new Soup.Session();
    }

    destroy() {}
}

export default class E extends Extension {
    enable() {
        this._client = new Client();
    }

    disable() {
        this._client = null;
    }
}
""".strip(),
                encoding="utf-8",
            )

            result = analyze_path(root)
            rule_ids = {finding.rule_id for finding in result.findings}
            self.assertIn("EGO-L-008", rule_ids)

    def test_entrypoint_local_class_refs_require_release(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"localref@example.com","name":"LocalRef","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "extension.js").write_text(
                """
import { Extension } from "resource:///org/gnome/shell/extensions/extension.js";

class Helper {
    destroy() {}
}

export default class E extends Extension {
    enable() {
        this._helper = new Helper();
    }

    disable() {
        this._helper.destroy();
    }
}
""".strip(),
                encoding="utf-8",
            )

            result = analyze_path(root)
            rule_ids = {finding.rule_id for finding in result.findings}
            self.assertIn("EGO-L-005", rule_ids)

    def test_gnome49_rules_are_version_gated(self) -> None:
        result = analyze_path(DATA_DIR / "gnome49_break")
        rule_ids = {finding.rule_id for finding in result.findings}
        self.assertIn("EGO-C49-001", rule_ids)
        self.assertIn("EGO-C49-002", rule_ids)
        self.assertIn("EGO-C49-003", rule_ids)
        self.assertIn("EGO-C49-004", rule_ids)
        self.assertIn("EGO-C49-005", rule_ids)

    def test_gnome50_rules_are_version_gated(self) -> None:
        result = analyze_path(DATA_DIR / "gnome50_break")
        rule_ids = {finding.rule_id for finding in result.findings}
        self.assertIn("EGO-C50-001", rule_ids)
        self.assertIn("EGO-C50-002", rule_ids)

    def test_prefs_import_graph_does_not_trigger_shell_import_rule(self) -> None:
        result = analyze_path(DATA_DIR / "prefs_import_context")
        rule_ids = {finding.rule_id for finding in result.findings}
        self.assertNotIn("EGO-I-002", rule_ids)

    def test_literal_dynamic_imports_are_included_in_context_graph(self) -> None:
        result = analyze_path(DATA_DIR / "dynamic_import_context")
        rule_ids = {finding.rule_id for finding in result.findings}
        self.assertNotIn("EGO-I-002", rule_ids)

    def test_legacy_imports_are_included_in_context_graph(self) -> None:
        result = analyze_path(DATA_DIR / "legacy_import_context")
        rule_ids = {finding.rule_id for finding in result.findings}
        self.assertNotIn("EGO-P-007", rule_ids)

    def test_reexport_chain_is_included_in_context_graph(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"reexport@example.com","name":"ReExport","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "extension.js").write_text(
                """
import { run } from "./src/index.js";

export default class E {
    enable() {
        run();
    }

    disable() {}
}
""".strip(),
                encoding="utf-8",
            )
            (root / "src").mkdir()
            (root / "src" / "index.js").write_text(
                """
export { run } from "./impl.js";
""".strip(),
                encoding="utf-8",
            )
            (root / "src" / "impl.js").write_text(
                """
export function run() {}
""".strip(),
                encoding="utf-8",
            )

            result = analyze_path(root)
            rule_ids = {finding.rule_id for finding in result.findings}
            self.assertNotIn("EGO-P-007", rule_ids)

    def test_unreachable_js_files_are_flagged(self) -> None:
        result = analyze_path(DATA_DIR / "unreachable_js")
        rule_ids = {finding.rule_id for finding in result.findings}
        self.assertIn("EGO-P-007", rule_ids)

    def test_owned_refs_should_be_released_after_cleanup(self) -> None:
        result = analyze_path(DATA_DIR / "release_owned_ref")
        rule_ids = {finding.rule_id for finding in result.findings}
        self.assertIn("EGO-L-005", rule_ids)

    def test_module_global_parent_owned_refs_should_still_be_released(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"global-release@example.com","name":"Global","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "extension.js").write_text(
                (
                    "import St from 'gi://St';\n"
                    "let parent;\n"
                    "let child;\n"
                    "export default class E {\n"
                    " enable() {\n"
                    "  parent = new St.BoxLayout();\n"
                    "  child = new St.Label({ text: 'x' });\n"
                    "  parent.set_child(child);\n"
                    " }\n"
                    " disable() {\n"
                    "  if (parent) { parent.destroy(); parent = null; }\n"
                    " }\n"
                    "}\n"
                ),
                encoding="utf-8",
            )

            result = analyze_path(root)
            rule_ids = {finding.rule_id for finding in result.findings}
            self.assertIn("EGO-L-005", rule_ids)

    def test_legacy_global_containers_should_be_released(self) -> None:
        result = analyze_path(DATA_DIR / "legacy_global_release")
        rule_ids = {finding.rule_id for finding in result.findings}
        self.assertIn("EGO-L-005", rule_ids)

    def test_legacy_global_scope_side_effects_are_flagged(self) -> None:
        result = analyze_path(DATA_DIR / "legacy_global_scope")
        rule_ids = {finding.rule_id for finding in result.findings}
        self.assertIn("EGO-L-001", rule_ids)

    def test_gjs_module_spawn_marks_target_as_reachable(self) -> None:
        result = analyze_path(DATA_DIR / "gjs_module_spawn")
        rule_ids = {finding.rule_id for finding in result.findings}
        self.assertNotIn("EGO-P-007", rule_ids)
        self.assertNotIn("EGO-I-002", rule_ids)

    def test_removed_apis_do_not_flag_without_target_version(self) -> None:
        result = analyze_path(DATA_DIR / "gnome48_ok")
        rule_ids = {finding.rule_id for finding in result.findings}
        self.assertNotIn("EGO-C49-001", rule_ids)
        self.assertNotIn("EGO-C49-002", rule_ids)
        self.assertNotIn("EGO-C49-003", rule_ids)
        self.assertNotIn("EGO-C49-004", rule_ids)
        self.assertNotIn("EGO-C49-005", rule_ids)
        self.assertNotIn("EGO-C50-001", rule_ids)
        self.assertNotIn("EGO-C50-002", rule_ids)

    def test_embedded_mode_uses_package_relative_paths(self) -> None:
        result = analyze_path(DATA_DIR / "bad_subprocess", path_mode="embedded")
        self.assertEqual(result.findings[0].evidence[0].path, "extension.js")
        self.assertEqual(result.artifacts["metadata_path"], "metadata.json")
        self.assertEqual(result.artifacts["root"], ".")

    def test_cli_mode_uses_zip_prefixed_paths_for_archives(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_path = Path(tmpdir) / "bad_subprocess.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                for path in (DATA_DIR / "bad_subprocess").rglob("*"):
                    if path.is_file():
                        archive.write(
                            path, arcname=path.relative_to(DATA_DIR / "bad_subprocess")
                        )

            result = analyze_path(archive_path, path_mode="cli")
            expected_prefix = f"{archive_path.resolve()}:"
            self.assertTrue(
                result.findings[0].evidence[0].path.startswith(expected_prefix)
            )
            self.assertEqual(
                result.findings[0].evidence[0].path,
                f"{archive_path.resolve()}:extension.js",
            )
            self.assertEqual(
                result.artifacts["metadata_path"],
                f"{archive_path.resolve()}:metadata.json",
            )
            self.assertEqual(result.artifacts["root"], str(archive_path.resolve()))

    def test_macosx_artifacts_are_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"artifact@example.com","name":"Artifact","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "extension.js").write_text(
                "export default class E { enable() {} disable() {} }", encoding="utf-8"
            )
            artifact_dir = root / "__MACOSX"
            artifact_dir.mkdir()
            (artifact_dir / "._extension.js").write_text("", encoding="utf-8")

            result = analyze_path(root)
            rule_ids = {finding.rule_id for finding in result.findings}
            self.assertIn("EGO-P-006", rule_ids)

    def test_screenshots_folder_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"screenshots@example.com","name":"Screenshots","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "extension.js").write_text(
                "export default class E { enable() {} disable() {} }",
                encoding="utf-8",
            )
            screenshots = root / "screenshots"
            screenshots.mkdir()
            (screenshots / "shot.png").write_bytes(b"x")

            result = analyze_path(root)
            rule_ids = {finding.rule_id for finding in result.findings}
            self.assertIn("EGO-P-006", rule_ids)

    def test_non_shell_shebang_in_sh_script_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"script-mismatch@example.com","name":"ScriptMismatch","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "extension.js").write_text(
                "export default class E { enable() {} disable() {} }",
                encoding="utf-8",
            )
            scripts = root / "scripts"
            scripts.mkdir()
            (scripts / "runner.sh").write_text(
                "#!/usr/bin/env python3\nimport time\nprint('ok')\n",
                encoding="utf-8",
            )

            result = analyze_path(root)
            findings = [
                finding for finding in result.findings if finding.rule_id == "EGO-P-006"
            ]
            self.assertTrue(
                any(
                    ".sh` scripts with a non-shell shebang" in finding.message
                    for finding in findings
                )
            )

    def test_shell_shebang_in_sh_script_is_not_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"shell-script@example.com","name":"ShellScript","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "extension.js").write_text(
                "export default class E { enable() {} disable() {} }",
                encoding="utf-8",
            )
            scripts = root / "scripts"
            scripts.mkdir()
            (scripts / "runner.sh").write_text(
                "#!/usr/bin/env bash\nprintf 'ok\\n'\n",
                encoding="utf-8",
            )

            result = analyze_path(root)
            findings = [
                finding for finding in result.findings if finding.rule_id == "EGO-P-006"
            ]
            self.assertFalse(
                any(
                    ".sh` scripts with a non-shell shebang" in finding.message
                    for finding in findings
                )
            )

    def test_symlinks_are_ignored_during_file_walk(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            outside = root.parent / "outside.js"
            outside.write_text("export const outside = 1;", encoding="utf-8")
            (root / "metadata.json").write_text(
                '{"uuid":"symlink@example.com","name":"Symlink","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "extension.js").write_text(
                "export default class E { enable() {} disable() {} }",
                encoding="utf-8",
            )
            (root / "leak.js").symlink_to(outside)

            result = analyze_path(root)
            self.assertEqual(result.artifacts["file_count"], 2)

    def test_zip_with_unsafe_member_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_path = Path(tmpdir) / "unsafe.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("../evil.js", "x")

            with self.assertRaisesRegex(ValueError, "unsafe path"):
                analyze_path(archive_path)

    def test_file_size_limit_is_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"limits@example.com","name":"Limits","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "extension.js").write_text("x" * 128, encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "file size limit"):
                analyze_path(root, limits=AnalysisLimits(max_file_size_bytes=64))

    def test_compiled_schemas_are_flagged_for_45_plus(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"compiled@example.com","name":"Compiled","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "extension.js").write_text(
                "export default class E { enable() {} disable() {} }",
                encoding="utf-8",
            )
            schema_dir = root / "schemas"
            schema_dir.mkdir()
            (schema_dir / "gschemas.compiled").write_bytes(b"x")

            result = analyze_path(root)
            findings = [
                finding for finding in result.findings if finding.rule_id == "EGO-P-006"
            ]
            self.assertTrue(
                any(
                    "Compiled GSettings schemas" in finding.message
                    for finding in findings
                )
            )

    def test_unlock_dialog_comment_warning_is_not_duplicated(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"unlock@example.com","name":"Unlock","description":"","shell-version":["46"],"session-modes":["user","unlock-dialog"]}',
                encoding="utf-8",
            )
            (root / "helper.js").write_text(
                "export const helper = 1;", encoding="utf-8"
            )
            (root / "extension.js").write_text(
                (
                    "import './helper.js';\n"
                    "export default class E { enable() {} disable() {} }"
                ),
                encoding="utf-8",
            )

            result = analyze_path(root)
            findings = [
                finding for finding in result.findings if finding.rule_id == "EGO-M-008"
            ]
            self.assertEqual(len(findings), 1)

    def test_nested_custom_class_timeout_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"nested@example.com","name":"Nested","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "extension.js").write_text(
                """
import GLib from 'gi://GLib';

class Worker {
    constructor() {
        this._updateId = GLib.timeout_add(
            GLib.PRIORITY_DEFAULT,
            100,
            () => GLib.SOURCE_REMOVE
        );
    }
}

export default class Extension {
    enable() {
        this._worker = new Worker();
    }

    disable() {
        this._worker = null;
    }
}
""".strip(),
                encoding="utf-8",
            )

            result = analyze_path(root)
            rule_ids = {finding.rule_id for finding in result.findings}
            self.assertIn("EGO-L-004", rule_ids)

    def test_untracked_timeout_source_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"timeout@example.com","name":"Timeout","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "extension.js").write_text(
                """
import GLib from 'gi://GLib';

export default class Extension {
    enable() {
        GLib.timeout_add(GLib.PRIORITY_DEFAULT, 100, () => GLib.SOURCE_REMOVE);
    }

    disable() {}
}
""".strip(),
                encoding="utf-8",
            )

            result = analyze_path(root)
            rule_ids = {finding.rule_id for finding in result.findings}
            self.assertIn("EGO-L-004", rule_ids)

    def test_untracked_signal_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"signal@example.com","name":"Signal","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "extension.js").write_text(
                """
export default class Extension {
    enable() {
        global.display.connect('window-created', () => {});
    }

    disable() {}
}
""".strip(),
                encoding="utf-8",
            )

            result = analyze_path(root)
            rule_ids = {finding.rule_id for finding in result.findings}
            self.assertIn("EGO-L-003", rule_ids)

    def test_untracked_connect_after_signal_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"signal-after@example.com","name":"SignalAfter","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "extension.js").write_text(
                """
export default class Extension {
    enable() {
        global.display.connect_after('window-created', () => {});
    }

    disable() {}
}
""".strip(),
                encoding="utf-8",
            )

            result = analyze_path(root)
            rule_ids = {finding.rule_id for finding in result.findings}
            self.assertIn("EGO-L-003", rule_ids)

    def test_duplicate_signal_findings_are_merged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"dupe-signal@example.com","name":"DupeSignal","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "extension.js").write_text(
                """
import GObject from "gi://GObject";
import { Extension } from "resource:///org/gnome/shell/extensions/extension.js";

class First extends GObject.Object {
    enable() {
        this._id1 = global.display.connect("window-created", () => {});
    }
}

class Second extends GObject.Object {
    enable() {
        this._id2 = global.display.connect("window-created", () => {});
    }
}

export default class E extends Extension {
    enable() {
        this._first = new First();
        this._second = new Second();
        this._first.enable();
        this._second.enable();
    }

    disable() {}
}
""".strip(),
                encoding="utf-8",
            )

            result = analyze_path(root)
            signal_findings = [
                finding for finding in result.findings if finding.rule_id == "EGO-L-003"
            ]
            self.assertEqual(len(signal_findings), 1)
            self.assertGreaterEqual(len(signal_findings[0].evidence), 2)

    def test_menu_owned_activate_signal_is_not_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"menu-signal@example.com","name":"MenuSignal","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "extension.js").write_text(
                """
import GObject from "gi://GObject";
import * as PanelMenu from "resource:///org/gnome/shell/ui/panelMenu.js";
import * as PopupMenu from "resource:///org/gnome/shell/ui/popupMenu.js";

const Indicator = GObject.registerClass(
class Indicator extends PanelMenu.Button {
    _init() {
        super._init(0.0, "Indicator");
        const item = new PopupMenu.PopupMenuItem("Run");
        item.connect("activate", () => {});
        this.menu.addMenuItem(item);
    }
});

export default class Extension {
    enable() {
        this._indicator = new Indicator();
    }

    disable() {
        this._indicator.destroy();
        this._indicator = null;
    }
}
""".strip(),
                encoding="utf-8",
            )

            result = analyze_path(root)
            rule_ids = {finding.rule_id for finding in result.findings}
            self.assertNotIn("EGO-L-003", rule_ids)

    def test_single_quoted_menu_owned_activate_signal_is_not_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"menu-signal-single@example.com","name":"MenuSignalSingle","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "extension.js").write_text(
                """
import GObject from "gi://GObject";
import * as PanelMenu from "resource:///org/gnome/shell/ui/panelMenu.js";
import * as PopupMenu from "resource:///org/gnome/shell/ui/popupMenu.js";

const Indicator = GObject.registerClass(
class Indicator extends PanelMenu.Button {
    _init() {
        super._init(0.0, "Indicator");
        const item = new PopupMenu.PopupImageMenuItem("Run", "system-run-symbolic");
        item.connect('activate', () => {});
        this.menu.addMenuItem(item);
    }
});

export default class Extension {
    enable() {
        this._indicator = new Indicator();
    }

    disable() {
        this._indicator.destroy();
        this._indicator = null;
    }
}
""".strip(),
                encoding="utf-8",
            )

            result = analyze_path(root)
            rule_ids = {finding.rule_id for finding in result.findings}
            self.assertNotIn("EGO-L-003", rule_ids)

    def test_menu_owned_child_widget_signal_is_not_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"menu-child-signal@example.com","name":"MenuChildSignal","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "extension.js").write_text(
                """
import GObject from "gi://GObject";
import St from "gi://St";
import * as PanelMenu from "resource:///org/gnome/shell/ui/panelMenu.js";
import * as PopupMenu from "resource:///org/gnome/shell/ui/popupMenu.js";

const Indicator = GObject.registerClass(
class Indicator extends PanelMenu.Button {
    _init() {
        super._init(0.0, "Indicator");
        this._button = new St.Button({ label: "Run" });
        this._button.connect("clicked", () => {});

        const box = new St.BoxLayout();
        box.add_child(this._button);

        const item = new PopupMenu.PopupBaseMenuItem({ reactive: false });
        item.add_child(box);
        this.menu.addMenuItem(item);
    }
});

export default class Extension {
    enable() {
        this._indicator = new Indicator();
    }

    disable() {
        this._indicator.destroy();
        this._indicator = null;
    }
}
""".strip(),
                encoding="utf-8",
            )

            result = analyze_path(root)
            rule_ids = {finding.rule_id for finding in result.findings}
            self.assertNotIn("EGO-L-003", rule_ids)

    def test_local_object_signal_is_not_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"local-object-signal@example.com","name":"LocalObjectSignal","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "extension.js").write_text(
                """
import GObject from "gi://GObject";
import St from "gi://St";
import * as PanelMenu from "resource:///org/gnome/shell/ui/panelMenu.js";

const Indicator = GObject.registerClass(
class Indicator extends PanelMenu.Button {
    _init() {
        super._init(0.0, "Indicator");
        const button = new St.Button({ label: "Run" });
        button.connect("clicked", () => {});
        this.add_child(button);
    }
});

export default class Extension {
    enable() {
        this._indicator = new Indicator();
    }

    disable() {
        this._indicator.destroy();
        this._indicator = null;
    }
}
""".strip(),
                encoding="utf-8",
            )

            result = analyze_path(root)
            rule_ids = {finding.rule_id for finding in result.findings}
            self.assertNotIn("EGO-L-003", rule_ids)

    def test_local_ui_widget_signal_is_not_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"local-ui-signal@example.com","name":"LocalUiSignal","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "prefs.js").write_text(
                """
import Gtk from "gi://Gtk";
import Adw from "gi://Adw";

export default class ExamplePrefs extends Adw.PreferencesWindow {
    _init() {
        super._init();

        const row = new Adw.ActionRow({ title: "Example" });
        const toggle = new Gtk.Switch({ active: true });
        toggle.connect("notify::active", widget => {
            row.set_sensitive(widget.get_active());
        });
        row.add_suffix(toggle);
        this.add(row);
    }
}
""".strip(),
                encoding="utf-8",
            )

            result = analyze_path(root)
            rule_ids = {finding.rule_id for finding in result.findings}
            self.assertNotIn("EGO-L-003", rule_ids)

    def test_helper_created_local_child_signal_is_not_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"helper-child@example.com","name":"HelperChild","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "extension.js").write_text(
                """
import St from "gi://St";

function createButton() {
    return new St.Button({ label: "Run" });
}

export default class Extension {
    enable() {
        const box = new St.BoxLayout();
        const btn = createButton();
        btn.connect("clicked", () => {});
        box.add_child(btn);
        this._box = box;
    }

    disable() {
        this._box.destroy();
        this._box = null;
    }
}
""".strip(),
                encoding="utf-8",
            )

            result = analyze_path(root)
            rule_ids = {finding.rule_id for finding in result.findings}
            self.assertNotIn("EGO-L-003", rule_ids)

    def test_field_owned_child_widgets_are_not_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"field-owned-children@example.com","name":"FieldOwnedChildren","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "extension.js").write_text(
                """
import GObject from "gi://GObject";
import St from "gi://St";
import * as PanelMenu from "resource:///org/gnome/shell/ui/panelMenu.js";

const Indicator = GObject.registerClass(
class Indicator extends PanelMenu.Button {
    _init() {
        super._init(0.0, "Indicator");
        this._container = new St.BoxLayout();

        const bottomArea = new St.BoxLayout();
        const inputArea = new St.BoxLayout();
        this._input = new St.Entry();
        this._input.clutter_text.connect("activate", () => {});
        inputArea.add_child(this._input);
        bottomArea.add_child(inputArea);
        this._container.add_child(bottomArea);
        this.add_child(this._container);
    }
});

export default class Extension {
    enable() {
        this._indicator = new Indicator();
    }

    disable() {
        this._indicator.destroy();
        this._indicator = null;
    }
}
""".strip(),
                encoding="utf-8",
            )

            result = analyze_path(root)
            rule_ids = {finding.rule_id for finding in result.findings}
            self.assertNotIn("EGO-L-003", rule_ids)
            self.assertNotIn("EGO-L-002", rule_ids)
            self.assertNotIn("EGO-L-005", rule_ids)

    def test_self_root_child_widgets_are_not_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"self-root-children@example.com","name":"SelfRootChildren","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "extension.js").write_text(
                """
import GObject from "gi://GObject";
import St from "gi://St";
import * as PanelMenu from "resource:///org/gnome/shell/ui/panelMenu.js";

const Indicator = GObject.registerClass(
class Indicator extends PanelMenu.Button {
    _init() {
        super._init(0.0, "Indicator");

        const header = new St.BoxLayout();
        this._tab = new St.Button({ label: "Tab" });
        this._tab.connect("clicked", () => {});
        header.add_child(this._tab);
        this.add_child(header);
    }
});

export default class Extension {
    enable() {
        this._indicator = new Indicator();
    }

    disable() {
        this._indicator.destroy();
        this._indicator = null;
    }
}
""".strip(),
                encoding="utf-8",
            )

            result = analyze_path(root)
            rule_ids = {finding.rule_id for finding in result.findings}
            self.assertNotIn("EGO-L-003", rule_ids)

    def test_add_child_wrapper_preserves_ui_ownership(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"add-child-wrapper@example.com","name":"AddChildWrapper","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "extension.js").write_text(
                """
import GObject from "gi://GObject";
import St from "gi://St";
import * as PanelMenu from "resource:///org/gnome/shell/ui/panelMenu.js";

const Utils = {
    addChildToParent(parent, child) {
        parent.add_child(child);
    },
};

const Indicator = GObject.registerClass(
class Indicator extends PanelMenu.Button {
    _init() {
        super._init(0.0, "Indicator");

        const buttonsBox = new St.BoxLayout();
        this.closeButton = new St.Button({ label: "Close" });
        this.closeButton.connect("clicked", () => {});
        buttonsBox.add_child(this.closeButton);

        const overlay = new St.BoxLayout();
        Utils.addChildToParent(overlay, buttonsBox);
        this.add_child(overlay);
    }
});

export default class Extension {
    enable() {
        this._indicator = new Indicator();
    }

    disable() {
        this._indicator.destroy();
        this._indicator = null;
    }
}
""".strip(),
                encoding="utf-8",
            )

            result = analyze_path(root)
            rule_ids = {finding.rule_id for finding in result.findings}
            self.assertNotIn("EGO-L-003", rule_ids)
            self.assertNotIn("EGO-L-002", rule_ids)
            self.assertNotIn("EGO-L-005", rule_ids)

    def test_popup_menu_section_actor_is_framework_owned(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"popup-menu-section-owned@example.com","name":"PopupMenuSectionOwned","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "extension.js").write_text(
                """
import St from "gi://St";
import * as PopupMenu from "resource:///org/gnome/shell/ui/popupMenu.js";
import { Extension } from "resource:///org/gnome/shell/extensions/extension.js";

class WindowPreviewList extends PopupMenu.PopupMenuSection {
    constructor() {
        super();
        this.actor = new St.ScrollView();
        this.actor.connect("scroll-event", this._onScrollEvent.bind(this));
        this.grid = new St.Widget();
        this.box.add_child(this.grid);
    }

    _onScrollEvent() {}

    destroy() {
        super.destroy();
    }
}

export default class E extends Extension {
    enable() {
        this._list = new WindowPreviewList();
    }

    disable() {
        this._list.destroy();
        this._list = null;
    }
}
""".strip(),
                encoding="utf-8",
            )

            result = analyze_path(root)
            rule_ids = {finding.rule_id for finding in result.findings}
            self.assertNotIn("EGO-L-003", rule_ids)
            self.assertNotIn("EGO-L-002", rule_ids)
            self.assertNotIn("EGO-L-005", rule_ids)

    def test_transitive_child_menu_roots_are_framework_owned(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"child-menu@example.com","name":"ChildMenu","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "extension.js").write_text(
                """
import { Extension } from "resource:///org/gnome/shell/extensions/extension.js";

class PopupMenuSection {}

class ChildMenu extends PopupMenuSection {
    constructor() {
        super();
        this.menu = new PopupMenuSection();
    }
}

class CustomizeChildMenu extends ChildMenu {
    constructor() {
        super();
        this.actor.connect("destroy", () => this._destroy());
        this.menu.connect("open-state-changed", () => this._sync());
    }

    _destroy() {}
    _sync() {}
}

export default class E extends Extension {
    enable() {
        this._menu = new CustomizeChildMenu();
    }

    disable() {
        this._menu = null;
    }
}
""".strip(),
                encoding="utf-8",
            )

            result = analyze_path(root)
            self.assertNotIn(
                "EGO-L-003",
                {finding.rule_id for finding in result.findings},
            )

    def test_signal_handling_wrapper_is_treated_as_signal_group(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"signal-handling@example.com","name":"SignalHandling","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "extension.js").write_text(
                """
import GObject from "gi://GObject";
import St from "gi://St";
import { Extension } from "resource:///org/gnome/shell/extensions/extension.js";

class SignalHandling {
    connect(obj, key, fun) {
        return obj.connect(key, fun);
    }

    disconnect() {}
}

export default class E extends Extension {
    enable() {
        this._signals = new SignalHandling();
        this._button = new St.Button({ label: "Run" });
        this._signals.connect(this._button, "clicked", () => {});
    }

    disable() {
        this._signals.disconnect();
        this._button.destroy();
        this._button = null;
        this._signals = null;
    }
}
""".strip(),
                encoding="utf-8",
            )

            result = analyze_path(root)
            rule_ids = {finding.rule_id for finding in result.findings}
            self.assertNotIn("EGO-L-003", rule_ids)

    def test_signal_manager_destroy_is_treated_as_signal_group(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"signal-manager@example.com","name":"SignalManager","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "extension.js").write_text(
                """
import { Extension } from "resource:///org/gnome/shell/extensions/extension.js";

class SignalManager {
    connect(obj, signal, handler) {
        return obj.connect(signal, handler);
    }

    destroy() {}
}

export default class E extends Extension {
    enable() {
        this._signals = new SignalManager();
        this._signals.connect(global.display, "restacked", () => {});
    }

    disable() {
        this._signals.destroy();
    }
}
""".strip(),
                encoding="utf-8",
            )

            result = analyze_path(root)
            rule_ids = {finding.rule_id for finding in result.findings}
            self.assertNotIn("EGO-L-003", rule_ids)

    def test_settimeout_requires_cleartimeout(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"timeout@example.com","name":"Timeout","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "extension.js").write_text(
                """
export default class Extension {
    enable() {
        this._id = setTimeout(() => {}, 100);
    }

    disable() {}
}
""".strip(),
                encoding="utf-8",
            )

            result = analyze_path(root)
            rule_ids = {finding.rule_id for finding in result.findings}
            self.assertIn("EGO-L-004", rule_ids)

    def test_recreating_timeout_without_clear_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"timeout-recreate@example.com","name":"TimeoutRecreate","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "extension.js").write_text(
                """
export default class Extension {
    enable() {
        this._id = setTimeout(() => {}, 100);
        this._id = setTimeout(() => {}, 100);
    }

    disable() {
        clearTimeout(this._id);
    }
}
""".strip(),
                encoding="utf-8",
            )

            result = analyze_path(root)
            rule_ids = {finding.rule_id for finding in result.findings}
            self.assertIn("EGO-L-007", rule_ids)

    def test_placeholder_stylesheet_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"style@example.com","name":"Style","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "extension.js").write_text(
                "export default class E { enable() {} disable() {} }",
                encoding="utf-8",
            )
            (root / "stylesheet.css").write_text(
                "/* Add your custom extension styling here */",
                encoding="utf-8",
            )

            result = analyze_path(root)
            findings = [
                finding for finding in result.findings if finding.rule_id == "EGO-P-006"
            ]
            self.assertTrue(
                any(
                    "Package contains files that often should not be shipped"
                    in finding.message
                    for finding in findings
                )
            )

    def test_secret_schema_in_global_scope_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"secret@example.com","name":"Secret","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "prefs.js").write_text(
                """
const { Secret } = imports.gi;
let SCHEMA = new Secret.Schema('org.example', 0, {});
""".strip(),
                encoding="utf-8",
            )

            result = analyze_path(root)
            rule_ids = {finding.rule_id for finding in result.findings}
            self.assertIn("EGO-L-001", rule_ids)

    def test_shell_singleton_getters_in_global_scope_are_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"singleton@example.com","name":"Singleton","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "extension.js").write_text(
                """
import Shell from "gi://Shell";
import { Extension } from "resource:///org/gnome/shell/extensions/extension.js";

const appSystem = Shell.AppSystem.get_default();
const tracker = Shell.WindowTracker.get_default();

export default class E extends Extension {
    enable() {}
    disable() {}
}
""".strip(),
                encoding="utf-8",
            )

            result = analyze_path(root)
            rule_ids = {finding.rule_id for finding in result.findings}
            self.assertIn("EGO-L-001", rule_ids)

    def test_top_level_object_literal_is_not_flagged_as_pre_enable_resource(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"literal@example.com","name":"Literal","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "extension.js").write_text(
                """
const Phase = {
    get pomodoro() { return "Pomodoro"; },
    get short_break() { return "Short Break"; },
};

export default class Extension {
    enable() {}
    disable() {}
}
""".strip(),
                encoding="utf-8",
            )

            result = analyze_path(root)
            rule_ids = {finding.rule_id for finding in result.findings}
            self.assertNotIn("EGO-L-001", rule_ids)

    def test_legacy_helper_timeout_reachable_from_enable_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"legacy-timeout@example.com","name":"LegacyTimeout","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "extension.js").write_text(
                """
const GLib = imports.gi.GLib;

function init() {}

function enable() {
    _tick();
}

function disable() {}

function _tick() {
    GLib.timeout_add(GLib.PRIORITY_DEFAULT, 100, () => GLib.SOURCE_REMOVE);
}
""".strip(),
                encoding="utf-8",
            )

            result = analyze_path(root)
            rule_ids = {finding.rule_id for finding in result.findings}
            self.assertIn("EGO-L-004", rule_ids)

    def test_runtime_method_anonymous_timeout_requires_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"runtime-timeout@example.com","name":"RuntimeTimeout","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "extension.js").write_text(
                """
import GLib from "gi://GLib";
import { Extension } from "resource:///org/gnome/shell/extensions/extension.js";

export default class E extends Extension {
    enable() {}

    trigger() {
        GLib.timeout_add(GLib.PRIORITY_DEFAULT, 10, () => GLib.SOURCE_REMOVE);
    }

    disable() {}
}
""".strip(),
                encoding="utf-8",
            )

            result = analyze_path(root)
            rule_ids = {finding.rule_id for finding in result.findings}
            self.assertIn("EGO-L-004", rule_ids)

    def test_bound_this_method_timeout_requires_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"bound-timeout@example.com","name":"BoundTimeout","description":"","shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "extension.js").write_text(
                """
import GLib from "gi://GLib";
import { Extension } from "resource:///org/gnome/shell/extensions/extension.js";

export default class E extends Extension {
    enable() {
        this._tick();
    }

    _tick() {
        this._loop = GLib.timeout_add_seconds(
            GLib.PRIORITY_DEFAULT,
            1,
            this._tick.bind(this)
        );
    }

    disable() {}
}
""".strip(),
                encoding="utf-8",
            )

            result = analyze_path(root)
            rule_ids = {finding.rule_id for finding in result.findings}
            self.assertIn("EGO-L-004", rule_ids)


class LifecycleEgo014Test(unittest.TestCase):
    """EGO_L_002 — objects created in enable() must be destroyed in disable()."""

    _METADATA = (
        '{"uuid":"ego014@example.com","name":"EGO-L-002",'
        '"description":"","shell-version":["46"]}'
    )

    def _make_pkg(self, tmpdir: str, extension_js: str) -> Path:
        root = Path(tmpdir)
        (root / "metadata.json").write_text(self._METADATA, encoding="utf-8")
        (root / "extension.js").write_text(extension_js.strip(), encoding="utf-8")
        return root

    def test_st_widget_not_destroyed_triggers_ego014(self) -> None:
        """St widget created in enable() but only nulled, never destroyed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._make_pkg(
                tmpdir,
                """
import St from "gi://St";
import { Extension } from "resource:///org/gnome/shell/extensions/extension.js";
export default class E extends Extension {
    enable() {
        this._label = new St.Label({ text: "hello" });
    }
    disable() {
        this._label = null;
    }
}
""",
            )
            result = analyze_path(root)
            rule_ids = {f.rule_id for f in result.findings}
            self.assertIn("EGO-L-002", rule_ids)

    def test_st_widget_properly_destroyed_suppresses_ego014(self) -> None:
        """St widget destroyed before null release must not trigger EGO_L_002."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._make_pkg(
                tmpdir,
                """
import St from "gi://St";
import { Extension } from "resource:///org/gnome/shell/extensions/extension.js";
export default class E extends Extension {
    enable() {
        this._label = new St.Label({ text: "hello" });
    }
    disable() {
        this._label.destroy();
        this._label = null;
    }
}
""",
            )
            result = analyze_path(root)
            rule_ids = {f.rule_id for f in result.findings}
            self.assertNotIn("EGO-L-002", rule_ids)


class CrossFileLifecycleTest(unittest.TestCase):
    """
    Cross-file lifecycle tests.

    Tests marked with the comment "# Phase 6" document behaviour that
    requires cross-file method_reachability and are expected to FAIL until
    Phase 6 is implemented.  All other tests must pass on the current
    codebase.
    """

    _METADATA = (
        '{"uuid":"xfile@example.com","name":"XFile",'
        '"description":"","shell-version":["46"]}'
    )

    def _make_pkg(self, root: Path, extension_js: str, helper_js: str) -> None:
        (root / "metadata.json").write_text(self._METADATA, encoding="utf-8")
        (root / "extension.js").write_text(extension_js.strip(), encoding="utf-8")
        (root / "helper.js").write_text(helper_js.strip(), encoding="utf-8")

    # ------------------------------------------------------------------
    # Regression tests — must pass before and after Phase 6
    # ------------------------------------------------------------------

    def test_cross_file_signal_with_cleanup_does_not_trigger_ego015(self) -> None:
        """Imported helper assigns and disconnects signal via `this`-parameter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._make_pkg(
                root,
                extension_js="""
import { connectAll, disconnectAll } from "./helper.js";
import { Extension } from "resource:///org/gnome/shell/extensions/extension.js";
export default class E extends Extension {
    enable() { connectAll(this); }
    disable() { disconnectAll(this); }
}
""",
                helper_js="""
export function connectAll(ext) {
    ext._signalId = global.display.connect("notify::focus-window", () => {});
}
export function disconnectAll(ext) {
    global.display.disconnect(ext._signalId);
    ext._signalId = null;
}
""",
            )
            result = analyze_path(root)
            rule_ids = {f.rule_id for f in result.findings}
            self.assertNotIn("EGO-L-003", rule_ids)

    def test_cross_file_source_with_cleanup_does_not_trigger_ego016(self) -> None:
        """Imported helper adds and removes GLib source via `this`-parameter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._make_pkg(
                root,
                extension_js="""
import { startTimer, stopTimer } from "./helper.js";
import { Extension } from "resource:///org/gnome/shell/extensions/extension.js";
export default class E extends Extension {
    enable() { startTimer(this); }
    disable() { stopTimer(this); }
}
""",
                helper_js="""
import GLib from "gi://GLib";
export function startTimer(ext) {
    ext._timerId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 60, () => {
        return GLib.SOURCE_CONTINUE;
    });
}
export function stopTimer(ext) {
    if (ext._timerId) {
        GLib.source_remove(ext._timerId);
        ext._timerId = null;
    }
}
""",
            )
            result = analyze_path(root)
            rule_ids = {f.rule_id for f in result.findings}
            self.assertNotIn("EGO-L-004", rule_ids)

    # ------------------------------------------------------------------
    # Phase 6 tests — currently fail; must pass after Phase 6
    # ------------------------------------------------------------------

    def test_cross_file_signal_without_cleanup_triggers_ego015(self) -> None:
        """Imported helper assigns signal via `this`-parameter but never disconnects.

        Phase 6: extension.js analysis must follow connectAll() into helper.js,
        discover ext._signalId assignment, and flag the missing disconnect.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._make_pkg(
                root,
                extension_js="""
import { connectAll } from "./helper.js";
import { Extension } from "resource:///org/gnome/shell/extensions/extension.js";
export default class E extends Extension {
    enable() { connectAll(this); }
    disable() {}
}
""",
                helper_js="""
export function connectAll(ext) {
    ext._signalId = global.display.connect("notify::focus-window", () => {});
}
""",
            )
            result = analyze_path(root)
            rule_ids = {f.rule_id for f in result.findings}
            self.assertIn("EGO-L-003", rule_ids)  # Phase 6

    def test_cross_file_source_without_cleanup_triggers_ego016(self) -> None:
        """Imported helper adds GLib source via `this`-parameter but never removes it.

        Phase 6: extension.js analysis must follow startTimer() into helper.js,
        discover ext._timerId assignment, and flag the missing removal.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._make_pkg(
                root,
                extension_js="""
import { startTimer } from "./helper.js";
import { Extension } from "resource:///org/gnome/shell/extensions/extension.js";
export default class E extends Extension {
    enable() { startTimer(this); }
    disable() {}
}
""",
                helper_js="""
import GLib from "gi://GLib";
export function startTimer(ext) {
    ext._timerId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 60, () => {
        return GLib.SOURCE_CONTINUE;
    });
}
""",
            )
            result = analyze_path(root)
            rule_ids = {f.rule_id for f in result.findings}
            self.assertIn("EGO-L-004", rule_ids)  # Phase 6

    def test_cross_file_helper_cache_is_scoped_by_helper_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "a").mkdir()
            (root / "b").mkdir()
            a_entry = root / "a" / "entry.js"
            b_entry = root / "b" / "entry.js"
            a_helper = root / "a" / "helper.js"
            b_helper = root / "b" / "helper.js"

            a_entry.write_text(
                'import { connectAll } from "./helper.js";\nconnectAll(this);\n',
                encoding="utf-8",
            )
            b_entry.write_text(
                'import { connectAll } from "./helper.js";\nconnectAll(this);\n',
                encoding="utf-8",
            )
            a_helper.write_text(
                """
export function connectAll(ext) {
    ext._signalId = global.display.connect("notify::focus-window", () => {});
}
""".strip(),
                encoding="utf-8",
            )
            b_helper.write_text(
                """
export function connectAll(ext) {
    ext._timerId = 42;
}
""".strip(),
                encoding="utf-8",
            )

            indices = build_cross_file_indices_per_file([a_entry, b_entry])

            self.assertIn(a_entry, indices)
            self.assertIn(b_entry, indices)
            self.assertEqual(indices[a_entry]["connectAll"].path, a_helper)
            self.assertEqual(indices[b_entry]["connectAll"].path, b_helper)
            self.assertIn("_signalId", indices[a_entry]["connectAll"].source)
            self.assertIn("_timerId", indices[b_entry]["connectAll"].source)


class IterNodesTest(unittest.TestCase):
    def test_deep_nesting_does_not_raise_recursion_error(self) -> None:
        # Generate a JS expression with nesting depth well above Python's
        # default recursion limit (~1000) to verify the iterative traversal.
        source = "a" + "||a" * 2000
        tree = parse_js(source)
        nodes = list(iter_nodes(tree.root_node))
        self.assertGreater(len(nodes), 0)

    def test_preorder_traversal_order_is_preserved(self) -> None:
        source = "a + b"
        tree = parse_js(source)
        types = [n.type for n in iter_nodes(tree.root_node)]
        # Root (program) must come before its children
        self.assertEqual(types[0], "program")
        # binary_expression must appear before its operands
        bin_idx = types.index("binary_expression")
        ident_idx = types.index("identifier")
        self.assertLess(bin_idx, ident_idx)


class ValidateUuidTest(unittest.TestCase):
    def setUp(self) -> None:
        from shexli.analyzer.metadata import validate_uuid

        self.validate_uuid = validate_uuid

    def test_valid_uuid(self) -> None:
        self.assertTrue(self.validate_uuid("my-extension@example.com"))
        self.assertTrue(self.validate_uuid("ext@author.io"))
        self.assertTrue(self.validate_uuid("ext@nodot"))

    def test_missing_at(self) -> None:
        self.assertFalse(self.validate_uuid("noatsign"))

    def test_empty_local_part(self) -> None:
        self.assertFalse(self.validate_uuid("@example.com"))

    def test_gnome_org_rejected(self) -> None:
        self.assertFalse(self.validate_uuid("ext@gnome.org"))
        self.assertFalse(self.validate_uuid("ext@extensions.gnome.org"))

    def test_single_char_rejected(self) -> None:
        self.assertFalse(self.validate_uuid("a"))


class ParseVersionStringTest(unittest.TestCase):
    def setUp(self) -> None:
        from shexli.analyzer.metadata import InvalidShellVersion, parse_version_string

        self.parse = parse_version_string
        self.Invalid = InvalidShellVersion

    def test_modern_single_version(self) -> None:
        self.assertEqual(self.parse("46")[0], 46)
        self.assertEqual(self.parse("50")[0], 50)

    def test_four_component_is_rejected(self) -> None:
        with self.assertRaises(self.Invalid):
            self.parse("3.36.0.1")

    def test_three_component_pre40(self) -> None:
        major, minor, point = self.parse("3.36.2")
        self.assertEqual((major, minor, point), (3, 36, 2))

    def test_invalid_string_rejected(self) -> None:
        with self.assertRaises(self.Invalid):
            self.parse("not-a-version")


class ShebangInterpreterTest(unittest.TestCase):
    def setUp(self) -> None:
        from shexli.analyzer.package import _shebang_interpreter

        self.interp = _shebang_interpreter

    def test_plain_bash(self) -> None:
        self.assertEqual(self.interp("#!/bin/bash\n"), "bash")

    def test_env_bash(self) -> None:
        self.assertEqual(self.interp("#!/usr/bin/env bash\n"), "bash")

    def test_env_S_flag(self) -> None:
        self.assertEqual(self.interp("#!/usr/bin/env -S bash\n"), "bash")

    def test_env_u_flag_with_arg(self) -> None:
        self.assertEqual(self.interp("#!/usr/bin/env -u FOO bash\n"), "bash")

    def test_env_multiple_flags(self) -> None:
        self.assertEqual(self.interp("#!/usr/bin/env -u FOO -C /tmp bash\n"), "bash")

    def test_env_double_dash(self) -> None:
        self.assertEqual(self.interp("#!/usr/bin/env -- bash\n"), "bash")

    def test_env_python(self) -> None:
        self.assertEqual(self.interp("#!/usr/bin/env python3\n"), "python3")

    def test_empty_shebang(self) -> None:
        self.assertIsNone(self.interp("#!\n"))

    def test_no_shebang(self) -> None:
        self.assertIsNone(self.interp("echo hello\n"))


class GSettingsUsageAstTest(unittest.TestCase):
    """check_gsettings_usage must not fire on GSettings mentions in comments."""

    def _run(self, js_source: str) -> set[str]:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "metadata.json").write_text(
                '{"uuid":"gs-test@example.com","name":"GS","description":"",'
                '"shell-version":["46"]}',
                encoding="utf-8",
            )
            (root / "extension.js").write_text(js_source, encoding="utf-8")
            result = analyze_path(root)
            return {f.rule_id for f in result.findings}

    def test_gio_settings_in_code_triggers_ego011(self) -> None:
        rule_ids = self._run(
            'import Gio from "gi://Gio";\n'
            "const s = new Gio.Settings("
            "{schema_id: 'org.gnome.shell.extensions.gs-test'});\n"
        )
        self.assertIn("EGO-P-003", rule_ids)

    def test_gio_settings_in_comment_does_not_trigger_ego011(self) -> None:
        rule_ids = self._run(
            "// Uses Gio.Settings for preferences\n"
            "export default class E { enable() {} disable() {} }\n"
        )
        self.assertNotIn("EGO-P-003", rule_ids)

    def test_get_settings_call_triggers_ego011(self) -> None:
        rule_ids = self._run(
            'import { Extension } from "resource:///org/gnome/shell/extensions/extension.js";\n'
            "export default class E extends Extension {\n"
            "    enable() { this._s = this.getSettings(); }\n"
            "    disable() { this._s = null; }\n"
            "}\n"
        )
        self.assertIn("EGO-P-003", rule_ids)


class DonationUrlValidationTest(unittest.TestCase):
    def _run_with_donations(self, donations: dict) -> set[str]:
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            metadata = {
                "uuid": "don@example.com",
                "name": "D",
                "description": "",
                "shell-version": ["46"],
                "donations": donations,
            }
            (root / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
            result = analyze_path(root)
            return {f.rule_id for f in result.findings}

    def test_valid_custom_url_accepted(self) -> None:
        rule_ids = self._run_with_donations({"custom": "https://example.com/donate"})
        self.assertNotIn("EGO-M-007", rule_ids)

    def test_scheme_only_url_rejected(self) -> None:
        rule_ids = self._run_with_donations({"custom": "https://"})
        self.assertIn("EGO-M-007", rule_ids)

    def test_non_http_scheme_rejected(self) -> None:
        rule_ids = self._run_with_donations({"custom": "ftp://example.com/donate"})
        self.assertIn("EGO-M-007", rule_ids)


if __name__ == "__main__":
    unittest.main()
