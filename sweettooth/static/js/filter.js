"use strict";

require(['jquery', 'hashparamutils'], function($, hashparamutils) {

    function makeLink(name, value, text) {
        return $('<li>', {'class': 'filter-sort-ui-sort-link'}).
            text(text).
            click(function() {
                var hp = hashparamutils.getHashParams();
                hp[name] = value;
                hashparamutils.setHashParams(hp);
            });
    }

    var sortCriteria = {
        'name': "Name",
        'recent': "Recent",
        'downloads': "Downloads",
        'popularity': "Popularity"
    };

    $.fn.filterUIify = function() {

        return this.each(function() {
            var $elem = $(this);

            function closeUI() {
                if ($link.hasClass('selected')) {
                    $('.filter-ui').slideUp('fast', function() {
                        $(this).detach();
                    });
                    $link.removeClass('selected');
                    return true;
                }
                return false;
            }

            var $link = $('<a>', {'class': 'filter-ui-link'}).
                text("Filtering and Sorting").
                click(function() {
                    if (closeUI()) {
                        return false;
                    } else {
                        $(this).addClass('selected');
                        var pos = $elem.offset();
                        var $filterUI = $('<div>', {'class': 'filter-ui'}).
                            css({'top': pos.top + $elem.outerHeight(),
                                 'left': pos.left,
                                 'width': $elem.outerWidth()}).
                            appendTo(document.body).
                            hide().
                            slideDown('fast');

                        var $sortUI = $('<div>', {'class': 'filter-sort-ui'}).
                            appendTo($filterUI).
                            append('<h4>Sort by</h4>');

                        var $sortUL = $('<ul>').appendTo($sortUI);

                        var sortLinks = {};
                        $.each(sortCriteria, function(key) {
                            sortLinks[key] = makeLink('sort', key, this).
                                appendTo($sortUI).
                                click(function() {
                                    closeUI();
                                });
                        });

                        var hp = hashparamutils.getHashParams();
                        if (hp.sort === undefined)
                            hp.sort = 'name';

                        if (sortLinks.hasOwnProperty(hp.sort))
                            sortLinks[hp.sort].addClass('selected');

                        return false;
                    }
                }).appendTo($elem);

            $(document.body).click(function() {
                if (closeUI())
                    return false;
            });
        });
    };
});
