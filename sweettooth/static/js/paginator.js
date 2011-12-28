"use strict";

define(['jquery', 'jquery.hashchange'], function($) {

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

                $beforePaginator = buildPaginator();
                $afterPaginator = buildPaginator();

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
                             'href': '#' + makeHashParams(hp)}).text(text);
        }

        function buildPaginator() {
            var number = hashParams.page;
            var contextLeft = Math.max(number-context, 2);
            var contextRight = Math.min(number+context+2, numPages);

            var $elem = $('<div>', {'class': 'paginator'});

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

                if (numPages - (number+context) > 1)
                    $elem.append($('<span>', {'class': 'ellipses'}).text("..."));

                makeLink(numPages, 'last').appendTo($elem);
                makeLink(number+1, 'prev', "Next").appendTo($elem);
            }

            return $elem;
        }

        function hashChanged(hp) {
            if (hashParams.sort !== hp.sort)
                return true;

            if (hashParams.page !== hp.page)
                return true;

            return false;
        }

        $(window).hashchange(function() {
            var hp = getHashParams();
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
