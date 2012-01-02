"use strict";

define([], function() {

    function getHashParams() {
        var hash = window.location.hash;
        if (!hash)
            return {};

        var values = hash.slice(1).split('&');
        var obj = {};
        for (var i = 0; i < values.length; i++) {
            if (!values[i])
                continue;

            var kv = values[i].split('=');
            obj[kv[0]] = kv[1];
        }

        return obj;
    }

    function makeHashParams(obj) {
        var hash = '';
        for (var key in obj) {
            hash += key + '=' + obj[key] + '&';
        }

        // Remove last '&'
        return hash.slice(0, -1);
    }

    function setHashParams(obj) {
        window.location.hash = makeHashParams(obj);
    }

    return { getHashParams: getHashParams,
             makeHashParams: makeHashParams,
             setHashParams: setHashParams };

});
