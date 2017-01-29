// -*- mode: js; js-indent-level: 4; indent-tabs-mode: nil -*-

define(['jquery', 'messages', 'modal', 'hashParamUtils',
        'templates', 'extensions', 'uploader', 'fsui',
        'jquery.cookie', 'jquery.jeditable',
        'jquery.timeago', 'jquery.raty', 'jquery.colorbox'],
function($, messages, modal, hashParamUtils, templates) {
    "use strict";

    if (!$.ajaxSettings.headers)
        $.ajaxSettings.headers = {};

    $.ajaxSettings.headers['X-CSRFToken'] = $.cookie('csrftoken');

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

        $("#new_display_name").each(function() {
            var pk = $(this).data('pk');
            $(this).csrfEditable('/accounts/change_display_name/' + pk);
        });

        var $userPopupLink = $('#global_domain_bar .user');
        var $userPopup = $('#global_domain_bar .user_popup');
        function closeUserSettings() {
            if ($userPopupLink.hasClass('active')) {
                $userPopupLink.removeClass('active');
                $userPopup.animate({ top: '10px', opacity: 0 }, 200, function() {
                    $(this).hide();
                });
                return true;
            }
        }

        $userPopupLink.click(function() {
            $userPopupLink.addClass('active');
            $userPopup.
                show().
                css({ top: '-10px', opacity: 0 }).
                animate({ top: '0', opacity: 1 }, 200);
            modal.activateModal($userPopup, closeUserSettings);
            return false;
        });

        $('#local_extensions').addLocalExtensions();
        $('.extension.single-page').addExtensionSwitch();

        $.extend($.fn.raty.defaults, {
            path: '/static/images/',
            starOff: 'star-empty.png',
            starOn: 'star-full.png',
            size: 25
        });

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
                $('#leave_comment, #leave_rating').removeClass('selected');
                $(this).addClass('selected');
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

        var term = "";
        $('#search_input').on('input', function() {
            var newTerm = $.trim($(this).val());

            if (newTerm != term) {
                term = newTerm;
                // On a new search parameter, reset page to 0.
                hashParamUtils.setHashParam('page', undefined);
                $extensionsList.trigger('load-page');
            }
        });

        $('#error_report').fillInErrors();

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
                $ext.data('svm', data.svm);
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
                    var $newContent = $('<div>').append(templates.get('extensions/comments_list')(data));
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
