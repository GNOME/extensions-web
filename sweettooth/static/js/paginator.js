"use strict";

define(['jquery', 'hashparamutils', 'jquery.hashchange'], function($, hashparamutils) {

    $.fn.paginatorify = function(url, context) {
        if (!this.length)
            return this;

        var hashParams = {};

        if (context === undefined)
            context = 3;

        var $loadingPageContent = $('<div>', {'class': 'loading-page'}).
            text("Loading page... please wait");

        var $elem = $(this);
        var numPages = 0;
        var $beforePaginator = null;
        var $afterPaginator = null;

        function loadPage() {
            $elem.addClass('loading');
            $loadingPageContent.prependTo($elem);

            $.ajax({
                url: url,
                dataType: 'json',
                data: hashParams,
                type: 'GET'
            }).done(function(result) {
                if ($beforePaginator)
                    $beforePaginator.detach();
                if ($afterPaginator)
                    $afterPaginator.detach();

                $loadingPageContent.detach();

                numPages = result.numpages;

                $beforePaginator = buildPaginator().addClass('before-paginator');
                $afterPaginator = buildPaginator().addClass('after-paginator');

                var $newContent = $(result.html);

                $elem.
                    removeClass('loading').
                    empty().
                    append($beforePaginator).
                    append($newContent).
                    append($afterPaginator).
                    trigger('page-loaded');
            });
        }

        function makeLink(pageNumber, styleClass, text) {
            styleClass = styleClass === undefined ? "" : styleClass;
            text = text === undefined ? pageNumber.toString() : text;

            var hp = $.extend({}, hashParams);
            hp.page = pageNumber;

            return $('<a>', {'class': 'number ' + styleClass,
                             'href': '#' + hashparamutils.makeHashParams(hp)}).text(text);
        }

        function buildPaginator() {
            var number = hashParams.page;
            var contextLeft = Math.max(number-context, 2);
            var contextRight = Math.min(number+context+2, numPages);

            var $elem = $('<div>', {'class': 'paginator-content'});

            if (number > 1) {
                makeLink(number-1, 'prev', "Previous").appendTo($elem);
                makeLink(1, 'first').appendTo($elem);
                if (number-context > 2)
                    $elem.append($('<span>', {'class': 'ellipses'}).text("..."));

                for (var i = contextLeft; i < number; i++)
                    makeLink(i).appendTo($elem);
            }

            $elem.append($('<span>', {'class': 'current number'}).text(number));

            if (number < numPages) {
                for (var i = number+1; i < contextRight; i++)
                    makeLink(i).appendTo($elem);

                if (numPages - (number+context) > 2)
                    $elem.append($('<span>', {'class': 'ellipses'}).text("..."));

                makeLink(numPages, 'last').appendTo($elem);
                makeLink(number+1, 'prev', "Next").appendTo($elem);
            }

            return $('<div>', {'class': 'paginator'}).append($elem);
        }

        function hashChanged(hp) {
            if (hashParams.sort !== hp.sort)
                return true;

            if (hashParams.page !== hp.page)
                return true;

            return false;
        }

        $(window).hashchange(function() {
            var hp = hashparamutils.getHashParams();
            if (hp.page === undefined)
                hp.page = 1;
            else
                hp.page = parseInt(hp.page);

            if (hashChanged(hp)) {
                hashParams = hp;
                loadPage();
            }
        });

        $(window).hashchange();

        return this;
    };

});
