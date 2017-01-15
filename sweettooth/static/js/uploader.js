// -*- mode: js; js-indent-level: 4; indent-tabs-mode: nil -*-

/*
    Replaces img src value with changed input value
 */
define(['jquery'], function($) {
    "use strict";

    $.fn.uploadify = function(url) {
        var $elem = $(this), $input = $elem.find('input[type=file]').first();

        var BOUNDARY = ' -- 598275094719306587185414';
        // Stolen from http://demos.hacks.mozilla.org/openweb/imageUploader/js/extends/xhr.js
        function buildMultipart(filedata) {
            var body = '--' + BOUNDARY;

            body += '\r\nContent-Disposition: form-data; name=\"file\"';
            body += '; filename=\"file\"\r\nContent-type: image/png';
            body += '\r\n\r\n' + filedata + '\r\n--' + BOUNDARY;

            return body;
        }

        function uploadComplete(result) {
            var $old = $elem.find('img').first();
            if($old.length == 0)
            {
                $elem.prepend(
                    $('<a />')
                        .prop('href', result)
                        .append(
                            $('<img />')
                                .prop('src', result)
                        )
                );
            }
            else
            {
                $old.prop('src', result);
                $elem.removeClass('placeholder');

                if ($old.parent().is('a'))
                {
                    $old.parent().prop('href', result);
                }
            }
        }

        $input.on('change', function(e) {
            var dt, file;
            if (e.originalEvent.dataTransfer)
                dt = e.originalEvent.dataTransfer;
            else
                dt = this;

            file = dt.files[0];

            if (!file)
                return false;

            if (window.FormData) {
                var fd = new FormData();
                fd.append('file', file);

                var df = $.ajax(url, { type: 'POST',
                                       // Let the XMLHttpRequest figure out the mimetype from the FormData
                                       // http://dvcs.w3.org/hg/xhr/raw-file/tip/Overview.html#the-send%28%29-method
                                       contentType: false,
                                       processData: false,
                                       data: fd });
                df.done(uploadComplete);
            } else {
                var filereader = new FileReader();
                filereader.onload = function(e) {
                    var url = e.target.result;
                    var df = $.ajax(url, { type: 'POST',
                                           contentType: 'multipart/form-data; boundary="' + BOUNDARY + '"',
                                           data: buildMultipart(url) });
                    df.done(uploadComplete);
                };
                filereader.readAsBinaryString(file);
            }

            return false;
        });
    };
});
