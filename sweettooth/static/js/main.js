"use strict";

require(['jquery', 'messages', 'extensions', 'uploader',
         'jquery.cookie', 'jquery.jeditable',
         'jquery.timeago', 'jquery.rating'], function($, messages) {
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
                                { select: true,
                                  onblur: 'submit',
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

        $("abbr.timestamp").timeago();

        function closeUserSettings() {
            var needsClose = $('#global_domain_bar .user').hasClass('active');
            if (!needsClose)
                return false;

            $('#global_domain_bar .user').removeClass('active');
            $('#global_domain_bar .user_settings, #global_domain_bar .login_popup_form').animate({ top: '10px', opacity: 0 }, 200, function() {
                $(this).hide();
            });
            return true;
        }

        function openUserSettings() {
            $('#global_domain_bar .user').addClass('active');
            $('#global_domain_bar .user_settings, #global_domain_bar .login_popup_form').show().css({ top: '-10px', opacity: 0 }).animate({ top: '0', opacity: 1 }, 200);
        }

        $(document.body).click(function() {
            if (closeUserSettings())
                return false;
        });

        $('#global_domain_bar .user_settings, #global_domain_bar .login_popup_form').click(function(e) {
            e.stopPropagation();
        });

        $('#global_domain_bar .user').click(function() {
            if ($(this).hasClass('active')) {
                closeUserSettings();
            } else {
                openUserSettings();
            }
            return false;
        });

        $('#submit-ajax').click(function() {
            var $elem = $(this);

            var df = $.ajax({ url: $elem.data('url'),
                              type: 'POST' });
            df.done(function() {
                messages.addInfo("Your extension has been submitted.").hide().slideDown();
            });

            return false;
        });

        $('#local_extensions').addLocalExtensions();
        $('.extension.single-page').addExtensionSwitch();
        $('.comment .rating').each(function() {
            $(this).find('input').rating();
        });
        $('form .rating').rating();

        $('.expandy_header').click(function() {
            $(this).toggleClass('expanded').next().slideToggle();
        }).not('.expanded').next().hide();

        $('#extension_shell_versions_info').buildShellVersionsInfo();

        $('#extensions-list').
            paginatorify('/ajax/extensions-list/').
            bind('page-loaded', function() {
                $('li.extension').addOutOfDateIndicator();
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

        $('div.extension').checkForUpdates();

        var pk = $('.extension.single-page.can-edit').data('epk');
        if (pk) {
            var inlineEditURL = '/ajax/edit/' + pk;
            $('#extension_name, #extension_url').csrfEditable(inlineEditURL);
            $('#extension_description').csrfEditable(inlineEditURL, {type: 'textarea'});

            $('.screenshot.upload').uploadify('/ajax/upload/screenshot/'+pk+'?geometry=300x200');
            $('.icon.upload').uploadify('/ajax/upload/icon/'+pk);
        }

        var uuid = $('.extension').data('uuid');
        if (uuid) {
            var $brd = $('.binary-rating div');
            var ratingClick = function(action) {
                return function() {
                    if ($(this).hasClass('depressed'))
                        return;

                    var d = $.ajax({ type: 'POST',
                                     url: '/ajax/adjust-rating/',
                                     data: { uuid: uuid,
                                             action: action }});

                    d.done(function(result) {
                        $('.binary-rating-stats-likes').css('width', result.like_percent + '%');
                        $('.binary-rating-stats-dislikes').css('width', result.dislike_percent + '%');
                    });

                    $brd.removeClass('depressed');
                    $(this).addClass('depressed');
                };
            };

            $('.binary-rating-like').click(ratingClick('like'));
            $('.binary-rating-dislike').click(ratingClick('dislike'));
        }
    });
});
