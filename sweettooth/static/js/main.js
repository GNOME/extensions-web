/*
    GNOME Shell extensions repository
    Copyright (C) 2011-2013  Jasper St. Pierre <jstpierre@mecheye.net>
    Copyright (C) 2016-2019  Yuri Konotopov <ykonotopov@gnome.org>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
 */

define(['jquery', 'messages', 'modal', 'hashParamUtils',
        'template!extensions/comments_list', 'staticfiles', 'js.cookie', 'extensions', 'uploader', 'fsui', 'settings',
        'jquery.jeditable', 'jquery.timeago', 'jquery.raty', 'jquery.colorbox'],
function($, messages, modal, hashParamUtils, commentsTemplate, staticfiles, cookie) {
    "use strict";

    if (!$.ajaxSettings.headers)
        $.ajaxSettings.headers = {};

    $.ajaxSettings.headers['X-CSRFToken'] = cookie.get('csrftoken');

    $.fn.csrfEditable = function(url, options) {
        return $(this).each(function() {
            var $elem = $(this);

            function error(xhr, status, error) {
                if (status == 403) {
                    $elem.css("background-color", "#fcc");
                }
            }

            $elem.editable(url, $.extend(options || {},
                                { onblur: 'submit',
                                  ajaxoptions: { error: error, dataType: 'json' },
                                  callback: function(result, settings) {
                                      $elem.text(result);
                                  },
                                  data: function(string, settings) {
                                      return $.trim(string);
                                  }}));
            $elem.addClass("editable");
        });
    };

    $(document).ready(function() {
        // Make the login link activatable.
        $("#login_link").click(function(event) {
            $(this).toggleClass('selected');
            $("#login_popup_form").slideToggle();
            return false;
        });

        // Prevent double click on registration button
        $('form#registration').on('submit', function(event) {
        	$("form#registration button[type='submit']").prop('disabled', true);
        	return true;
        });

        // Add lightbox for screenshots
        $('div.extension-details').on('click', 'div.screenshot > a', function(event) {
            event.preventDefault();

            $.colorbox({
                href: $(this).prop('href'),
                maxWidth: '80%',
                maxHeight: '80%'
            });
        });

        $("time").timeago();

        $('#shell_settings').addShellSettings();
        $('#local_extensions').addLocalExtensions();
        $('.extension.single-page').addExtensionSwitch();
        $('.extension.single-page').addDownloadOptions();

        $.extend($.fn.raty.defaults, {
            starType: 'i',
            size: 25
        });

        if (staticfiles.getImage('images/star-empty.png'))
        {
            $.fn.raty.defaults.starOff = staticfiles.getImageFile('images/star-empty.png');
        }

        if (staticfiles.getImage('images/star-full.png'))
        {
            $.fn.raty.defaults.starOn = staticfiles.getImageFile('images/star-full.png');
        }

        $.fn.ratify = function() {
            return this.each(function() {
                $(this).raty({
                    score: $(this).data('rating-value'),
                    readOnly: true
                });
            });
        };

        let rating_initial = $('#rating_form').find('input[name="rating_initial"]');

        $('.comment .rating').ratify();
        $('#rating_form:not(.preview)').hide();
        $('#rating_form .rating').raty({
            scoreName: 'rating',
            score: rating_initial.length > 0 ? rating_initial.val() : undefined
        });

        if($('#rating_form input[name="show_rating"]').val() == '1')
        {
            $('#rating_form').find('.rating').show();
        }
        else
        {
            $('#rating_form').find('.rating').hide();
        }

        function makeShowForm(isRating) {
            return function() {
                $('#leave_comment, #leave_rating').removeClass('active');
                $(this).addClass('active');
                var $rating = $('#rating_form').slideDown().find('.rating');
                if (isRating)
				{
					$rating.show();
					$('#rating_form input[name="show_rating"]').val('1');
				}
                else
				{
					$rating.hide();
					$('#rating_form input[name="show_rating"]').val('0');
				}
            };
        }

        $('#leave_comment').click(makeShowForm(false));
        $('#leave_rating').click(makeShowForm(true));

        $('.expandy_header').click(function() {
            $(this).toggleClass('expanded').next().slideToggle();
        }).not('.expanded').next().hide();

        $('#extension_shell_versions_info').buildShellVersionsInfo();

        var $extensionsList = $('#extensions-list').
            paginatorify().
            on('page-loaded', function() {
                $('li.extension').grayOutIfOutOfDate();

                // If we're searching, don't add FSUI for now.
                if (!$('search_input').val())
                    $('#extensions-list .before-paginator').fsUIify();

                // Scroll the page back up to the top.
                document.documentElement.scrollTop = 0; // Firefox
                document.body.scrollTop = 0; // WebKit
            }).trigger('load-page');

        let term = "";
        let timeout_id = null;
        $('#search_input').on('input', function() {
            let newTerm = $.trim($(this).val());

            if (newTerm == term) {
                return;
            }

            term = newTerm;

            if(timeout_id) {
                clearTimeout(timeout_id);
            }

            timeout_id = setTimeout(() => {
                timeout_id = null;
                hashParamUtils.setHashParam('page', undefined);
                $extensionsList.trigger('load-page');
            }, 1000);
        });

        $('.extension_status_toggle a').click(function() {
            var $link = $(this);
            var $tr = $link.parents('tr');
            var href = $link.attr('href');
            var pk = $tr.data('pk');
            var $ext = $link.parents('.extension');

            var req = $.ajax({
                type: 'GET',
                dataType: 'json',
                data: { pk: pk },
                url: href
            });

            req.done(function(data) {
                $ext.data('svm', JSON.parse(data.svm));
                $('#extension_shell_versions_info').buildShellVersionsInfo();
                $tr.find('.mvs').html(data.mvs);
                $tr.find('.extension_status_toggle').toggleClass('visible');
            });

            return false;
        });

        $('.extension.single-page').each(function() {
            var pk = $(this).data('epk');
            if ($(this).hasClass('can-edit')) {
                var inlineEditURL = '/ajax/edit/' + pk;
                $('#extension_name, #extension_url').csrfEditable(inlineEditURL);
                $('#extension_description').csrfEditable(inlineEditURL, {type: 'textarea'});

                $('.screenshot .upload').parent().uploadify('/ajax/upload/screenshot/'+pk);
                $('.icon.upload').uploadify('/ajax/upload/icon/'+pk);
            }

            function fetchComments(base, showAll) {
                var $loading = base.find('.loading');
                $loading.show();

                $.ajax({
                    type: 'GET',
                    dataType: 'json',
                    data: { pk: pk, all: showAll },
                    url: '/comments/all/',
                }).done(function(comments) {
                    var $commentsHolder = base.find('.comments-holder');

                    $loading.hide();

                    if (comments.length < 5)
                        showAll = false;

                    var data = { comments: comments, show_all: showAll };
                    var $newContent = $('<div>').append(commentsTemplate.render(data));
                    $newContent.addClass('comments-holder');

                    $newContent.find('time').timeago();
                    $newContent.find('.rating').ratify();
                    $newContent.find('.show-all').on('click', function() {
                        $(this).hide();
                        fetchComments(base, true);
                    });

                    $commentsHolder.replaceWith($newContent);
                });
            }

            $(this).find('#comments').each(function() {
                fetchComments($(this), false);
            });
        });
    });
});
