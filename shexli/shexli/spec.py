# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from enum import StrEnum

from .models import RuleSpec


class RuleCode(StrEnum):
    EGO001 = "EGO001"
    EGO002 = "EGO002"
    EGO003 = "EGO003"
    EGO004 = "EGO004"
    EGO005 = "EGO005"
    EGO006 = "EGO006"
    EGO007 = "EGO007"
    EGO008 = "EGO008"
    EGO009 = "EGO009"
    EGO010 = "EGO010"
    EGO011 = "EGO011"
    EGO012 = "EGO012"
    EGO013 = "EGO013"
    EGO014 = "EGO014"
    EGO015 = "EGO015"
    EGO016 = "EGO016"
    EGO017 = "EGO017"
    EGO018 = "EGO018"
    EGO019 = "EGO019"
    EGO020 = "EGO020"
    EGO021 = "EGO021"
    EGO022 = "EGO022"
    EGO023 = "EGO023"
    EGO024 = "EGO024"
    EGO025 = "EGO025"
    EGO026 = "EGO026"
    EGO027 = "EGO027"
    EGO028 = "EGO028"
    EGO029 = "EGO029"
    EGO030 = "EGO030"
    EGO031 = "EGO031"
    EGO032 = "EGO032"
    EGO033 = "EGO033"
    EGO034 = "EGO034"
    EGO035 = "EGO035"
    EGO036 = "EGO036"
    EGO037 = "EGO037"
    EGO038 = "EGO038"
    EGO039 = "EGO039"
    EGO_C49_001 = "EGO-C49-001"
    EGO_C49_002 = "EGO-C49-002"
    EGO_C49_003 = "EGO-C49-003"
    EGO_C49_004 = "EGO-C49-004"
    EGO_C49_005 = "EGO-C49-005"
    EGO_C50_001 = "EGO-C50-001"
    EGO_C50_002 = "EGO-C50-002"


R = RuleCode

SPEC_VERSION = "2026-04-02"
GUIDELINES_URL = "https://gjs.guide/extensions/review-guidelines/review-guidelines.html"

RULES = [
    RuleSpec(
        rule_id=RuleCode.EGO001,
        title="metadata.json must exist",
        severity="error",
        source_url=f"{GUIDELINES_URL}#metadata-json-must-be-well-formed",
        source_section="metadata.json must be well-formed",
        static_checkable=True,
        detection_strategy="package-level required file check",
        rationale="Every extension ships metadata.json and review depends on it.",
    ),
    RuleSpec(
        rule_id=RuleCode.EGO002,
        title="metadata.json must be valid JSON",
        severity="error",
        source_url=f"{GUIDELINES_URL}#metadata-json-must-be-well-formed",
        source_section="metadata.json must be well-formed",
        static_checkable=True,
        detection_strategy="JSON parse",
        rationale="Malformed metadata blocks review and installation.",
    ),
    RuleSpec(
        rule_id=RuleCode.EGO003,
        title="metadata uuid must have valid format and namespace",
        severity="error",
        source_url=f"{GUIDELINES_URL}#metadata-json-must-be-well-formed",
        source_section="metadata.json must be well-formed",
        static_checkable=True,
        detection_strategy="regex validation for uuid and forbidden namespace",
        rationale=(
            "UUID format and namespace are explicitly constrained by "
            "GNOME review rules."
        ),
    ),
    RuleSpec(
        rule_id=RuleCode.EGO004,
        title=(
            "metadata shell-version must only include plausible stable "
            "releases and at most one development release"
        ),
        severity="error",
        source_url=f"{GUIDELINES_URL}#metadata-json-must-be-well-formed",
        source_section="metadata.json must be well-formed",
        static_checkable=True,
        detection_strategy="array validation with version token parsing",
        rationale="Extensions must not claim future shell support.",
    ),
    RuleSpec(
        rule_id=RuleCode.EGO005,
        title="metadata session-modes must be omitted when only user mode is declared",
        severity="warning",
        source_url=f"{GUIDELINES_URL}#metadata-json-must-be-well-formed",
        source_section="metadata.json must be well-formed",
        static_checkable=True,
        detection_strategy="metadata key presence and exact values check",
        rationale="Single user mode must not be redundantly declared.",
    ),
    RuleSpec(
        rule_id=RuleCode.EGO006,
        title="metadata session-modes may only contain user and unlock-dialog",
        severity="error",
        source_url=f"{GUIDELINES_URL}#metadata-json-must-be-well-formed",
        source_section="metadata.json must be well-formed",
        static_checkable=True,
        detection_strategy="allowed value set validation",
        rationale="Only two session modes are valid for published extensions.",
    ),
    RuleSpec(
        rule_id=RuleCode.EGO007,
        title="metadata donations may only contain allowed keys",
        severity="error",
        source_url=f"{GUIDELINES_URL}#metadata-json-must-be-well-formed",
        source_section="metadata.json must be well-formed",
        static_checkable=True,
        detection_strategy=(
            "strict validation against mirrored ego donation types and "
            "value constraints"
        ),
        rationale=(
            "Donation types and shapes are deterministic in ego metadata handling."
        ),
    ),
    RuleSpec(
        rule_id=RuleCode.EGO008,
        title="extensions using unlock-dialog must document it in disable() comments",
        severity="warning",
        source_url=f"{GUIDELINES_URL}#session-modes",
        source_section="Session Modes",
        static_checkable=True,
        detection_strategy="metadata and disable-body comment heuristic",
        rationale="unlock-dialog requires reviewer justification and extra caution.",
    ),
    RuleSpec(
        rule_id=RuleCode.EGO009,
        title="GSettings schema id must use org.gnome.shell.extensions base",
        severity="error",
        source_url=f"{GUIDELINES_URL}#gsettings-schemas",
        source_section="GSettings Schemas",
        static_checkable=True,
        detection_strategy="XML attribute inspection",
        rationale="Schema namespace is fixed by review rules.",
    ),
    RuleSpec(
        rule_id=RuleCode.EGO010,
        title="GSettings schema path must use /org/gnome/shell/extensions base",
        severity="error",
        source_url=f"{GUIDELINES_URL}#gsettings-schemas",
        source_section="GSettings Schemas",
        static_checkable=True,
        detection_strategy="XML attribute inspection",
        rationale="Schema path is fixed by review rules.",
    ),
    RuleSpec(
        rule_id=RuleCode.EGO011,
        title="GSettings schema XML must be present in package",
        severity="error",
        source_url=f"{GUIDELINES_URL}#gsettings-schemas",
        source_section="GSettings Schemas",
        static_checkable=True,
        detection_strategy="cross-check schema usage against package contents",
        rationale="Schema XML must ship in the extension package.",
    ),
    RuleSpec(
        rule_id=RuleCode.EGO012,
        title="GSettings schema XML filename must match schema id",
        severity="error",
        source_url=f"{GUIDELINES_URL}#gsettings-schemas",
        source_section="GSettings Schemas",
        static_checkable=True,
        detection_strategy="schema filename pattern validation",
        rationale="Reviewer expects exact `<schema-id>.gschema.xml` naming.",
    ),
    RuleSpec(
        rule_id=RuleCode.EGO013,
        title=(
            "extension must not create GObject instances or modify shell "
            "before enable()"
        ),
        severity="warning",
        source_url=f"{GUIDELINES_URL}#only-use-initialization-for-static-resources",
        source_section="Only use initialization for static resources",
        static_checkable=True,
        detection_strategy=(
            "AST detection of top-level or constructor-time resource "
            "creation and signal/source setup"
        ),
        rationale=("Initialization must stay free of runtime shell modifications."),
    ),
    RuleSpec(
        rule_id=RuleCode.EGO014,
        title="objects created by extension should be destroyed in disable()",
        severity="warning",
        source_url=f"{GUIDELINES_URL}#destroy-all-objects",
        source_section="Destroy all objects",
        static_checkable=True,
        detection_strategy=(
            "AST tracking of `this.<field> = new ...` in enable() and "
            "`this.<field>.destroy()` in disable()"
        ),
        rationale="Cleanup leaks are a central review concern.",
    ),
    RuleSpec(
        rule_id=RuleCode.EGO015,
        title="signals connected by extension should be disconnected in disable()",
        severity="warning",
        source_url=f"{GUIDELINES_URL}#disconnect-all-signals",
        source_section="Disconnect all signals",
        static_checkable=True,
        detection_strategy=(
            "AST tracking of `this.<field> = ...connect(...)` in enable() "
            "and matching disconnects in disable()"
        ),
        rationale="Signal leaks are common and reviewable statically.",
    ),
    RuleSpec(
        rule_id=RuleCode.EGO016,
        title="main loop sources should be removed in disable()",
        severity="warning",
        source_url=f"{GUIDELINES_URL}#remove-main-loop-sources",
        source_section="Remove main loop sources",
        static_checkable=True,
        detection_strategy=(
            "AST tracking of `this.<field> = GLib.timeout_add*` or "
            "idle_add and matching removals in disable()"
        ),
        rationale="Unremoved sources can outlive the extension lifecycle.",
    ),
    RuleSpec(
        rule_id=RuleCode.EGO017,
        title="deprecated modules must not be imported",
        severity="error",
        source_url=f"{GUIDELINES_URL}#do-not-use-deprecated-modules",
        source_section="Do not use deprecated modules",
        static_checkable=True,
        detection_strategy=(
            "AST import detection including ES modules and legacy imports.* usage"
        ),
        rationale="Deprecated modules are explicitly disallowed.",
    ),
    RuleSpec(
        rule_id=RuleCode.EGO018,
        title="Gtk, Gdk and Adw must not be imported in shell process files",
        severity="error",
        source_url=f"{GUIDELINES_URL}#do-not-import-gtk-libraries-in-gnome-shell",
        source_section="Do not import GTK libraries in GNOME Shell",
        static_checkable=True,
        detection_strategy="AST import detection in non-prefs JS files",
        rationale="GTK libraries conflict with shell process libraries.",
    ),
    RuleSpec(
        rule_id=RuleCode.EGO019,
        title="Clutter, Meta, St and Shell must not be imported in prefs process files",
        severity="error",
        source_url=f"{GUIDELINES_URL}#do-not-import-gnome-shell-libraries-in-preferences",
        source_section="Do not import GNOME Shell libraries in Preferences",
        static_checkable=True,
        detection_strategy="AST import detection in prefs.js and prefs modules",
        rationale="Shell libraries conflict with preferences process libraries.",
    ),
    RuleSpec(
        rule_id=RuleCode.EGO020,
        title="extension code must not be minified or obfuscated",
        severity="manual_review",
        source_url=f"{GUIDELINES_URL}#code-must-not-be-obfuscated",
        source_section="Code must not be obfuscated",
        static_checkable=True,
        detection_strategy=(
            "heuristic: average identifier length < 2 on files with > 500 bytes"
        ),
        rationale=(
            "Reviewers cannot audit obfuscated code; minification and name "
            "mangling are explicitly disallowed."
        ),
    ),
    RuleSpec(
        rule_id=RuleCode.EGO021,
        title="extension must not log excessively",
        severity="manual_review",
        source_url=f"{GUIDELINES_URL}#no-excessive-logging",
        source_section="No excessive logging",
        static_checkable=False,
        detection_strategy=(
            "deferred until policy-level logging thresholds are defined in ego"
        ),
        rationale=(
            "Excessive is policy-dependent; the current module avoids "
            "heuristic thresholds."
        ),
    ),
    RuleSpec(
        rule_id=RuleCode.EGO022,
        title="binary executables and libraries must not be bundled",
        severity="error",
        source_url=f"{GUIDELINES_URL}#scripts-and-binaries",
        source_section="Scripts and Binaries",
        static_checkable=True,
        detection_strategy="file extension and executable magic heuristic",
        rationale="Binary payloads are explicitly disallowed.",
    ),
    RuleSpec(
        rule_id=RuleCode.EGO023,
        title="telemetry tools must not be used",
        severity="manual_review",
        source_url=f"{GUIDELINES_URL}#do-not-use-telemetry-tools",
        source_section="Do not use telemetry tools",
        static_checkable=False,
        detection_strategy=(
            "deferred until telemetry signatures are formalized without "
            "keyword heuristics"
        ),
        rationale=(
            "This rule should be enforced with a curated signature "
            "database, not token guesses."
        ),
    ),
    RuleSpec(
        rule_id=RuleCode.EGO024,
        title=(
            "privileged subprocesses should use pkexec and target "
            "non-user-writable files"
        ),
        severity="warning",
        source_url=f"{GUIDELINES_URL}#privileged-subprocess-must-not-be-user-writable",
        source_section="Privileged Subprocess must not be user-writable",
        static_checkable=True,
        detection_strategy=(
            "AST detection of explicit privileged wrappers in subprocess "
            "APIs; file writability remains manual-review-only"
        ),
        rationale=(
            "Direct use of sudo-like wrappers is statically observable "
            "even if full target provenance is not."
        ),
    ),
    RuleSpec(
        rule_id=RuleCode.EGO025,
        title="unnecessary build and translation artifacts should not be shipped",
        severity="warning",
        source_url=f"{GUIDELINES_URL}#don-t-include-unnecessary-files",
        source_section="Don't include unnecessary files",
        static_checkable=True,
        detection_strategy="package file pattern scan",
        rationale="Reviewers may reject packages with unreasonable extra data.",
    ),
    RuleSpec(
        rule_id=RuleCode.EGO026,
        title="JavaScript files should be reachable from extension.js or prefs.js",
        severity="warning",
        source_url=f"{GUIDELINES_URL}#don-t-include-unnecessary-files",
        source_section="Don't include unnecessary files",
        static_checkable=True,
        detection_strategy="import graph reachability from extension.js and prefs.js",
        rationale=(
            "Shipped JS modules that are unreachable from known entrypoints "
            "are usually unnecessary package contents."
        ),
    ),
    RuleSpec(
        rule_id=RuleCode.EGO027,
        title="owned object references should be released in disable()",
        severity="warning",
        source_url=f"{GUIDELINES_URL}#destroy-all-objects",
        source_section="Destroy all objects",
        static_checkable=True,
        detection_strategy=(
            "AST tracking of `this.<field> = ...` in enable(), cleanup "
            "calls in disable(), and matching `this.<field> = "
            "null/undefined` release"
        ),
        rationale=(
            "Examples in the guidelines release owned references after "
            "cleanup, which reduces stale state across re-enable cycles."
        ),
    ),
    RuleSpec(
        rule_id=RuleCode.EGO028,
        title="extensions should not use synchronous subprocess APIs in shell code",
        severity="warning",
        source_url="https://gjs.guide/guides/gio/subprocesses.html",
        source_section="Complete Examples",
        static_checkable=True,
        detection_strategy=(
            "AST detection of synchronous GLib subprocess calls in shell context"
        ),
        rationale=(
            "Synchronous subprocess APIs can block the shell main loop and "
            "freeze the session."
        ),
    ),
    RuleSpec(
        rule_id=RuleCode.EGO029,
        title="extensions should not call run_dispose in extension code",
        severity="warning",
        source_url=(
            "https://gjs-docs.gnome.org/gobject20~2.0/gobject.object#method-run_dispose"
        ),
        source_section="GObject.Object.run_dispose",
        static_checkable=True,
        detection_strategy="AST detection of run_dispose() calls",
        rationale=(
            "run_dispose() is intended for object system implementations, "
            "not extension lifecycle cleanup."
        ),
    ),
    RuleSpec(
        rule_id=RuleCode.EGO030,
        title="extensions should avoid synchronous file IO in shell code",
        severity="warning",
        source_url="https://gjs.guide/guides/gio/file-operations.html",
        source_section="File Operations",
        static_checkable=True,
        detection_strategy=(
            "AST detection of synchronous file read APIs in shell context"
        ),
        rationale=(
            "Synchronous file IO can block the shell main loop and should "
            "be replaced with async file APIs."
        ),
    ),
    RuleSpec(
        rule_id=RuleCode.EGO031,
        title="extensions should not use imports._gi directly",
        severity="warning",
        source_url="https://gjs.guide/extensions/topics/extension.html#injectionmanager",
        source_section="InjectionManager",
        static_checkable=True,
        detection_strategy="AST and text detection of imports._gi usage",
        rationale=(
            "Direct use of imports._gi is discouraged in extensions and "
            "should be replaced with supported extension APIs."
        ),
    ),
    RuleSpec(
        rule_id=RuleCode.EGO032,
        title=(
            "45+ preferences should use fillPreferencesWindow instead of "
            "getPreferencesWidget"
        ),
        severity="warning",
        source_url=(
            "https://gjs.guide/extensions/upgrading/gnome-shell-45.html#preferences"
        ),
        source_section="Preferences",
        static_checkable=True,
        detection_strategy=(
            "AST detection of getPreferencesWidget() in prefs code gated by "
            "45+ target versions"
        ),
        rationale=(
            "GNOME Shell 45+ preferences code should use "
            "fillPreferencesWindow() rather than getPreferencesWidget()."
        ),
    ),
    RuleSpec(
        rule_id=RuleCode.EGO033,
        title=(
            "preferences classes should not retain window-scoped objects on "
            "instance fields without close-request cleanup"
        ),
        severity="warning",
        source_url=f"{GUIDELINES_URL}#destroy-all-objects",
        source_section="Destroy all objects",
        static_checkable=True,
        detection_strategy=(
            "AST detection of `this.<field>` or `this.#field` assignments in "
            "`fillPreferencesWindow()` without matching `close-request` cleanup"
        ),
        rationale=(
            "Preferences windows are short-lived and reviewers often reject "
            "code that stores UI or settings objects on the exported prefs "
            "class without cleanup on window close."
        ),
    ),
    RuleSpec(
        rule_id=RuleCode.EGO034,
        title="extensions should not manually load the default stylesheet.css",
        severity="warning",
        source_url="https://gjs.guide/extensions/overview/anatomy.html#stylesheet-css",
        source_section="`stylesheet.css`",
        static_checkable=True,
        detection_strategy=(
            "AST detection of `theme.load_stylesheet()` or "
            "`theme.unload_stylesheet()` on the default stylesheet.css"
        ),
        rationale=(
            "GNOME Shell automatically loads the packaged stylesheet.css, so "
            "manual load/unload code is usually unnecessary and reviewable."
        ),
    ),
    RuleSpec(
        rule_id=RuleCode.EGO035,
        title="main loop sources should be removed before being recreated",
        severity="warning",
        source_url=f"{GUIDELINES_URL}#remove-main-loop-sources",
        source_section="Remove main loop sources",
        static_checkable=True,
        detection_strategy=(
            "AST detection of repeated source assignments to the same field "
            "without an intervening remove/clear call"
        ),
        rationale=(
            "Reviewers often reject code that overwrites a stored timeout or "
            "idle source id before removing the previous source."
        ),
    ),
    RuleSpec(
        rule_id=RuleCode.EGO036,
        title=(
            "extensions should not use lookupByURL or lookupByUUID for "
            "current extension access"
        ),
        severity="warning",
        source_url=(
            "https://gjs.guide/extensions/upgrading/gnome-shell-45.html#extensionutils"
        ),
        source_section="`extensionUtils`",
        static_checkable=True,
        detection_strategy=(
            "AST detection of Extension or ExtensionPreferences "
            "lookupByURL()/lookupByUUID() calls in extension and prefs code"
        ),
        rationale=(
            "Current extension access should use `this`, `this.getSettings()` "
            "or `this.path` rather than lookup helpers in modern code."
        ),
    ),
    RuleSpec(
        rule_id=RuleCode.EGO037,
        title="Soup.Session instances should be aborted during cleanup",
        severity="warning",
        source_url=("https://gjs-docs.gnome.org/soup30~3.0/soup.session#method-abort"),
        source_section="Soup.Session.abort",
        static_checkable=True,
        detection_strategy=(
            "AST detection of `new Soup.Session()` assigned to instance "
            "fields without a matching `.abort()` call in cleanup methods"
        ),
        rationale=(
            "Retained Soup.Session instances should be aborted when the "
            "owning object or extension is destroyed."
        ),
    ),
    RuleSpec(
        rule_id=RuleCode.EGO038,
        title="extension files should not contain excessive ungated console logging",
        severity="warning",
        source_url=f"{GUIDELINES_URL}#no-excessive-logging",
        source_section="No excessive logging",
        static_checkable=True,
        detection_strategy=(
            "AST count of console.log/warn/error calls outside if-debug "
            "guards; threshold > 5 ungated calls per file"
        ),
        rationale=(
            "Excessive console output is noisy in production and may indicate "
            "forgotten debug instrumentation."
        ),
    ),
    RuleSpec(
        rule_id=RuleCode.EGO039,
        title="extensions should not access the clipboard directly",
        severity="manual_review",
        source_url=f"{GUIDELINES_URL}#clipboard-access-must-be-declared",
        source_section="Review Guidelines",
        static_checkable=True,
        detection_strategy="AST detection of St.Clipboard.get_default() calls",
        rationale=(
            "Direct clipboard access is a privacy concern and requires "
            "reviewer scrutiny."
        ),
    ),
    RuleSpec(
        rule_id=RuleCode.EGO_C49_001,
        title=(
            "extensions targeting GNOME 49 must not use "
            "DoNotDisturbSwitch from calendar.js"
        ),
        severity="error",
        source_url=(
            "https://gjs.guide/extensions/upgrading/gnome-shell-49.html"
            "#do-not-disturb-toggle"
        ),
        source_section="Do Not Disturb Toggle",
        static_checkable=True,
        detection_strategy=(
            "AST import detection gated by explicit shell-version membership for 49"
        ),
        rationale="DoNotDisturbSwitch is removed in GNOME Shell 49.",
    ),
    RuleSpec(
        rule_id=RuleCode.EGO_C49_002,
        title=(
            "extensions targeting GNOME 49 must not use removed Clutter action classes"
        ),
        severity="error",
        source_url=(
            "https://gjs.guide/extensions/upgrading/gnome-shell-49.html"
            "#clutter-clickaction-and-clutter-tapaction"
        ),
        source_section="Clutter.ClickAction() and Clutter.TapAction()",
        static_checkable=True,
        detection_strategy=(
            "AST detection of Clutter.ClickAction and Clutter.TapAction "
            "gated by explicit shell-version membership for 49"
        ),
        rationale="ClickAction and TapAction were removed in GNOME Shell 49.",
    ),
    RuleSpec(
        rule_id=RuleCode.EGO_C49_003,
        title=(
            "extensions targeting GNOME 49 must not call maximize or "
            "unmaximize with Meta.MaximizeFlags"
        ),
        severity="error",
        source_url="https://gjs.guide/extensions/upgrading/gnome-shell-49.html#meta-window",
        source_section="Meta.Window",
        static_checkable=True,
        detection_strategy=(
            "AST detection of maximize and unmaximize calls with "
            "Meta.MaximizeFlags arguments gated by explicit shell-version "
            "membership for 49"
        ),
        rationale=(
            "GNOME Shell 49 removed Meta.MaximizeFlags from maximize and "
            "unmaximize parameters."
        ),
    ),
    RuleSpec(
        rule_id=RuleCode.EGO_C49_004,
        title="extensions targeting GNOME 49 must not call Meta.Window.get_maximized",
        severity="error",
        source_url="https://gjs.guide/extensions/upgrading/gnome-shell-49.html#meta-window",
        source_section="Meta.Window",
        static_checkable=True,
        detection_strategy=(
            "AST detection of get_maximized() calls gated by explicit "
            "shell-version membership for 49"
        ),
        rationale="Meta.Window.get_maximized() was removed in GNOME Shell 49.",
    ),
    RuleSpec(
        rule_id=RuleCode.EGO_C49_005,
        title=(
            "extensions targeting GNOME 49 must not call "
            "Meta.CursorTracker.set_pointer_visible"
        ),
        severity="error",
        source_url="https://gjs.guide/extensions/upgrading/gnome-shell-49.html#meta-cursortracker",
        source_section="Meta.CursorTracker",
        static_checkable=True,
        detection_strategy=(
            "AST detection of set_pointer_visible() calls gated by "
            "explicit shell-version membership for 49"
        ),
        rationale=(
            "Meta.CursorTracker.set_pointer_visible() was replaced in GNOME Shell 49."
        ),
    ),
    RuleSpec(
        rule_id=RuleCode.EGO_C50_001,
        title=(
            "extensions targeting GNOME 50 must not rely on removed "
            "global.display restart signals"
        ),
        severity="error",
        source_url="https://gjs.guide/extensions/upgrading/gnome-shell-50.html#restart",
        source_section="Restart",
        static_checkable=True,
        detection_strategy=(
            "AST detection of global.display connect, disconnect, or emit "
            "calls using removed restart-related signals gated by "
            "explicit shell-version membership for 50"
        ),
        rationale=(
            "The restart-related global.display signals are no longer "
            "emitted in GNOME Shell 50."
        ),
    ),
    RuleSpec(
        rule_id=RuleCode.EGO_C50_002,
        title="extensions targeting GNOME 50 must not call RunDialog._restart",
        severity="error",
        source_url="https://gjs.guide/extensions/upgrading/gnome-shell-50.html#restart",
        source_section="Restart",
        static_checkable=True,
        detection_strategy=(
            "AST detection of _restart calls in code importing "
            "runDialog.js gated by explicit shell-version membership for 50"
        ),
        rationale="RunDialog._restart() was removed in GNOME Shell 50.",
    ),
]

RULES_BY_ID = {rule.rule_id: rule for rule in RULES}
