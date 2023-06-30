// -*- mode: js; js-indent-level: 4; indent-tabs-mode: nil -*-

define(['jquery', 'review'], function($) {
    "use strict";

    $(document).ready(function() {
        $("#files").reviewify(false);
        $("#diff").reviewify(true);
    });

    $('#diff_version_select').on('click', (event) => {
        event.stopPropagation();
    });

    $('#diff_version_select').on('change', (event) => {
        $("#diff").reviewify(true);
    });
});
