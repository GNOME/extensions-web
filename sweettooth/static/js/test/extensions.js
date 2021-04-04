require(['extensionUtils', 'jquery', 'test/qunit'], function(extensionUtils) {

    var grabProperExtensionVersion = extensionUtils.grabProperExtensionVersion;
    test("grabProperExtensionVersion", function() {
        var map = { "3.0": { version: 1, pk: 1 },
                    "3.0.1": { version: 2, pk: 2 },
                    "3.2.1": { version: 3, pk: 3 },
                    "3.2": { version: 4, pk: 4 },
                    "3.3": { version: 5, pk: 5 },
                    "3.3.1": { version: 6, pk: 6 },
                    "3.4.1": { version: 7, pk: 7 },
                    "40.alpha": { version: 8, pk: 8 },
                    "40": { version: 9, pk: 9 },
                    "40.7": { version: 10, pk: 10 },
        };

        equal(grabProperExtensionVersion(map, "3.4.0"), null);
        equal(grabProperExtensionVersion(map, "3.0.0").version, 1);
        equal(grabProperExtensionVersion(map, "3.0.1").version, 2);
        equal(grabProperExtensionVersion(map, "3.2.0").version, 4);
        equal(grabProperExtensionVersion(map, "3.2.1").version, 3);
        equal(grabProperExtensionVersion(map, "3.2.2").version, 4);
        equal(grabProperExtensionVersion(map, "3.3.0"), null, "stable release checking");
        equal(grabProperExtensionVersion(map, "3.3.1").version, 6);
        equal(grabProperExtensionVersion(map, "3.4.1.1").version, 7);
        equal(grabProperExtensionVersion(map, "40.alpha").version, 9);
        equal(grabProperExtensionVersion(map, "40.beta").version, 9);
        equal(grabProperExtensionVersion(map, "40.2").version, 9);
        equal(grabProperExtensionVersion(map, "40.7").version, 10);
    });

    test("getBestExtensionVersion", function() {
        var map = { "3.10": { version: 1, pk: 1 },
                    "3.13.4": { version: 2, pk: 2 },
                    "3.20": { version: 3, pk: 3 } };

        equal(grabProperExtensionVersion(map, "3.4.0", true).version, 1);
        equal(grabProperExtensionVersion(map, "3.7.4.1", true).version, 1);
        equal(grabProperExtensionVersion(map, "3.10.0", true).version, 1);
        equal(grabProperExtensionVersion(map, "3.13.4", true).version, 2);
        equal(grabProperExtensionVersion(map, "3.11.2", true).version, 3);
        equal(grabProperExtensionVersion(map, "3.20.0", true).version, 3);
        equal(grabProperExtensionVersion(map, "3.24.0", true).version, 3);
        equal(grabProperExtensionVersion(map, "40.14", true).version, 3);
    });

    function nhvEqual(versions, current, operation, stability, version) {
        var vm = {};
        versions.forEach(function(v) { vm[v] = true; });

        var nhv = findNextHighestVersion(vm, current);
        equal(nhv.operation, operation);

        if (operation === "stable") {
            equal(nhv.stability, stability);
            equal(nhv.version, version);
        }
    }

    var findNextHighestVersion = extensionUtils.findNextHighestVersion;
    test("findNextHighestVersion", function() {
        nhvEqual(["3.2"], "3.0.0", "upgrade", "stable", "3.2");
        nhvEqual(["3.2.1"], "3.0.0", "upgrade", "stable", "3.2");
        nhvEqual(["3.2.1", "3.0"], "3.2.0", "upgrade", "stable", "3.2.1");
        nhvEqual(["3.3", "3.0"], "3.2.0", "upgrade", "unstable", "3.3");
        nhvEqual(["3.2.1", "3.0", "3.3.1"], "3.2.0", "upgrade", "stable", "3.2.1");
        nhvEqual(["3.0"], "3.2.0", "downgrade");
    });
});
