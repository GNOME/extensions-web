# SPDX-License-Identifier: AGPL-3.0-or-later

import tempfile
import unittest
import zipfile
from pathlib import Path

from shexli import AnalysisLimits, analyze_path
from shexli.analyzer.evidence import node_evidence
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
        self.assertIn("EGO003", rule_ids)
        self.assertIn("EGO004", rule_ids)
        self.assertIn("EGO018", rule_ids)

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
        self.assertIn("EGO018", rule_ids)

    def test_good_cleanup_avoids_lifecycle_findings(self) -> None:
        result = analyze_path(DATA_DIR / "good_cleanup")
        rule_ids = {finding.rule_id for finding in result.findings}
        self.assertNotIn("EGO014", rule_ids)
        self.assertNotIn("EGO015", rule_ids)
        self.assertNotIn("EGO016", rule_ids)

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
            self.assertNotIn("EGO014", rule_ids)

    def test_glib_source_remove_counts_as_cleanup(self) -> None:
        result = analyze_path(DATA_DIR / "source_remove_cleanup")
        rule_ids = {finding.rule_id for finding in result.findings}
        self.assertNotIn("EGO016", rule_ids)

    def test_builtin_map_does_not_require_destroy(self) -> None:
        result = analyze_path(DATA_DIR / "builtin_map_cleanup")
        rule_ids = {finding.rule_id for finding in result.findings}
        self.assertNotIn("EGO014", rule_ids)

    def test_bad_donations_are_rejected(self) -> None:
        result = analyze_path(DATA_DIR / "bad_donations")
        rule_ids = [finding.rule_id for finding in result.findings]
        self.assertIn("EGO007", rule_ids)

    def test_bad_subprocess_is_flagged(self) -> None:
        result = analyze_path(DATA_DIR / "bad_subprocess")
        rule_ids = {finding.rule_id for finding in result.findings}
        self.assertIn("EGO024", rule_ids)

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
            self.assertIn("EGO024", rule_ids)

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
            self.assertIn("EGO024", rule_ids)

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
            self.assertIn("EGO024", rule_ids)

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
            self.assertIn("EGO028", rule_ids)

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
            self.assertIn("EGO029", rule_ids)

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
            self.assertIn("EGO030", rule_ids)

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
            self.assertIn("EGO031", rule_ids)

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
            self.assertIn("EGO032", rule_ids)

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
            self.assertNotIn("EGO032", rule_ids)

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
            self.assertIn("EGO033", rule_ids)

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
            self.assertNotIn("EGO033", rule_ids)

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
            self.assertIn("EGO027", rule_ids)

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
            self.assertIn("EGO013", rule_ids)
            self.assertIn("EGO027", rule_ids)

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
            self.assertIn("EGO027", rule_ids)

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
            self.assertIn("EGO034", rule_ids)

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
            self.assertIn("EGO036", rule_ids)

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
            self.assertIn("EGO037", rule_ids)

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
            self.assertIn("EGO027", rule_ids)

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
        self.assertNotIn("EGO018", rule_ids)

    def test_literal_dynamic_imports_are_included_in_context_graph(self) -> None:
        result = analyze_path(DATA_DIR / "dynamic_import_context")
        rule_ids = {finding.rule_id for finding in result.findings}
        self.assertNotIn("EGO018", rule_ids)

    def test_legacy_imports_are_included_in_context_graph(self) -> None:
        result = analyze_path(DATA_DIR / "legacy_import_context")
        rule_ids = {finding.rule_id for finding in result.findings}
        self.assertNotIn("EGO026", rule_ids)

    def test_unreachable_js_files_are_flagged(self) -> None:
        result = analyze_path(DATA_DIR / "unreachable_js")
        rule_ids = {finding.rule_id for finding in result.findings}
        self.assertIn("EGO026", rule_ids)

    def test_owned_refs_should_be_released_after_cleanup(self) -> None:
        result = analyze_path(DATA_DIR / "release_owned_ref")
        rule_ids = {finding.rule_id for finding in result.findings}
        self.assertIn("EGO027", rule_ids)

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
            self.assertIn("EGO027", rule_ids)

    def test_legacy_global_containers_should_be_released(self) -> None:
        result = analyze_path(DATA_DIR / "legacy_global_release")
        rule_ids = {finding.rule_id for finding in result.findings}
        self.assertIn("EGO027", rule_ids)

    def test_legacy_global_scope_side_effects_are_flagged(self) -> None:
        result = analyze_path(DATA_DIR / "legacy_global_scope")
        rule_ids = {finding.rule_id for finding in result.findings}
        self.assertIn("EGO013", rule_ids)

    def test_gjs_module_spawn_marks_target_as_reachable(self) -> None:
        result = analyze_path(DATA_DIR / "gjs_module_spawn")
        rule_ids = {finding.rule_id for finding in result.findings}
        self.assertNotIn("EGO026", rule_ids)
        self.assertNotIn("EGO018", rule_ids)

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
            self.assertIn("EGO025", rule_ids)

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
            self.assertIn("EGO025", rule_ids)

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
                finding for finding in result.findings if finding.rule_id == "EGO025"
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
                finding for finding in result.findings if finding.rule_id == "EGO025"
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
                finding for finding in result.findings if finding.rule_id == "EGO025"
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
                finding for finding in result.findings if finding.rule_id == "EGO008"
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
            self.assertIn("EGO016", rule_ids)

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
            self.assertIn("EGO016", rule_ids)

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
            self.assertIn("EGO015", rule_ids)

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
            self.assertIn("EGO015", rule_ids)

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
                finding for finding in result.findings if finding.rule_id == "EGO015"
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
            self.assertNotIn("EGO015", rule_ids)

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
            self.assertNotIn("EGO015", rule_ids)

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
            self.assertIn("EGO016", rule_ids)

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
            self.assertIn("EGO035", rule_ids)

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
                finding for finding in result.findings if finding.rule_id == "EGO025"
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
            self.assertIn("EGO013", rule_ids)

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
            self.assertIn("EGO013", rule_ids)

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
            self.assertNotIn("EGO013", rule_ids)

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
            self.assertIn("EGO016", rule_ids)

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
            self.assertIn("EGO016", rule_ids)

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
            self.assertIn("EGO016", rule_ids)


if __name__ == "__main__":
    unittest.main()
