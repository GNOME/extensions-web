// -*- mode: js; js-indent-level: 4; indent-tabs-mode: nil -*-

define(['jquery'], function($) {
    "use strict";

    var exports = {};

    // jQuery doesn't support events in the capturing phase natively.
    // This is a trick that fires jQuery's event handler during the
    // capturing phase.
    function captureHandler() {
        $.event.dispatch.apply(document.body, arguments);
    }

    exports.activateModal = function(elem, closeFunction) {
        $(document.body).on('click', function(e) {
            // If the user clicked inside the modal popup, don't
            // close it.
            if ($(elem).has(e.target).length) {
                return true;
            }

            if (closeFunction()) {
                $(document.body).off(e);
                document.body.removeEventListener('click', captureHandler, true);
                return false;
            }

            return true;
        });

        document.body.addEventListener('click', captureHandler, true);
    }

    return exports;
});
