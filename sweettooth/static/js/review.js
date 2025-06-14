// -*- mode: js; js-indent-level: 4; indent-tabs-mode: nil -*-

define(['jquery', 'diff'], function($, diff) {
    "use strict";

    var REVIEW_URL_BASE = '/review/ajax';

    var BINARY_TYPES = ['mo', 'compiled'];

    function isBinary(filename) {
        var parts = filename.split('.');
        var ext = parts[parts.length - 1];
        return BINARY_TYPES.indexOf(ext) >= 0;
    }

    function buildFileView(data) {
        if (data.raw)
            return $(data.html);

        var $table = $('<table>', {'class': 'code'});

        $.each(data.lines, function(i) {
            $table.append($('<tr>', {'class': 'line'}).
                          append($('<td>', {'class': 'linum'}).text(i + 1)).
                          append($('<td>', {'class': 'contents'}).html(this)));
        });

        return $table;
    }

    function compareVersionUrlPart() {
        let compare_version_pk = $('#diff_version_select').val();
        let compare_version_url = '';
        if(compare_version_pk) {
            compare_version_url = `/${compare_version_pk}`
        }

        return compare_version_url;
    }

    function createDiffView(filename, pk) {
        return $.ajax({
            type: 'GET',
            dataType: 'json',
            data: { filename: filename },
            url: `${REVIEW_URL_BASE}/get-file-diff/${pk}${compareVersionUrlPart()}`
        }).pipe(function(data) {
            return diff.buildDiffTable(data.chunks, data.oldlines, data.newlines);
        });
    }

    function createFileView(filename, pk) {
        return $.ajax({
            type: 'GET',
            dataType: 'json',
            data: { filename: filename },
            url: REVIEW_URL_BASE + '/get-file/' + pk
        }).pipe(function(data) {
            return buildFileView(data);
        });
    }

    function getFileClass(main_class, filename, files) {
        let classes = [main_class];

        if (files.symlinks.includes(filename)) {
            classes.push("symlink");
        }

        return classes.join(" ");
    }

    $.fn.reviewify = function(diff) {
        return this.each(function() {
            var $elem = $(this);
            $elem.empty();
            var $fileList = $('<ul>', {'class': 'filelist'}).appendTo($elem);
            var pk = $elem.data('pk');

            var $fileDisplay = $('<div>', {'class': 'filedisplay'}).appendTo($elem);
            $fileDisplay.css('position', 'relative');

            var currentFilename;
            var $currentFile = null;

            var req = $.ajax({
                type: 'GET',
                dataType: 'json',
                url: `${REVIEW_URL_BASE}/get-file-list/${pk}${compareVersionUrlPart()}`,
            });

            function showTable(filename, $file, $selector) {
                $fileList.find('li a.fileselector').removeClass('selected');
                $selector.addClass('selected');

                $file.css('position', 'relative');

                if ($currentFile != null) {
                    $currentFile.css({'position': 'absolute',
                                      'top': '0'});
                    $currentFile.fadeOut();
                    $file.fadeIn();
                } else {
                    $file.show();
                }

                currentFilename = filename;
                $currentFile = $file;
            }

            req.done(function(files) {
                function createFileSelector(tag, filename) {
                    var $selector = $('<a>').
                        addClass(tag).
                        addClass('fileselector').
                        text(filename);

                    var $file = null;

                    $('<li>').append($selector).appendTo($fileList);

                    if (isBinary(filename)) {
                        $selector.addClass('binary');
                        return;
                    }

                    $selector.click(function() {
                        if ($selector.hasClass('selected'))
                            return;

                        if ($file === null) {
                            var d = (diff ? createDiffView : createFileView)(filename, pk, diff);
                            currentFilename = filename;
                            d.done(function($table) {
                                $file = $table;
                                $file.hide().appendTo($fileDisplay);
                                if (currentFilename === filename)
                                    showTable(filename, $file, $selector);
                            });
                        } else {
                            showTable(filename, $file, $selector);
                        }

                    });
                }

                $.each(files.changed, function() { createFileSelector(getFileClass('changed', this, files), this); });
                $.each(files.added, function() { createFileSelector(getFileClass('added', this, files), this); });
                $.each(files.deleted, function() { createFileSelector(getFileClass('deleted', this, files), this); });

                // Don't show the 'unchanged' section in a diff view.
                if (!diff)
                    $.each(files.unchanged, function() { createFileSelector(getFileClass('unchanged', this, files), this); });

                // Select the first item.
                $fileList.find('li a.fileselector').first().click();
            });
        });
    };
});
