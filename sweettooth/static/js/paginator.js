/*
    GNOME Shell extensions repository
    Copyright (C) 2011-2012  Jasper St. Pierre <jstpierre@mecheye.net>
    Copyright (C) 2017-2019  Yuri Konotopov <ykonotopov@gnome.org>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
 */

define(['jquery', 'hashParamUtils', 'paginatorUtils', 'dbus!_',
		'template!extensions/info_list', 'template!extensions/info_contents', 'jquery.hashchange'],
		function ($, hashParamUtils, paginatorUtils, dbusProxy, infoTemplate, infoContentsTemplate) {
	"use strict";

	$.fn.paginatorify = function (context) {
		if (!this.length)
		{
			return this;
		}

		if (context === undefined)
		{
			context = 3;
		}

		var $elem = $(this);
		var $beforePaginator = null;
		var $afterPaginator = null;

		var currentRequest = null;

		function loadPage() {
			if (currentRequest !== null)
			{
				currentRequest.abort();
			}

			if ($beforePaginator !== null)
			{
				$beforePaginator.addClass('loading');
			}

			var queryParams = hashParamUtils.getHashParams();
			if (queryParams.page === undefined)
			{
				queryParams.page = 1;
			}

			if (queryParams.shell_version === undefined)
			{
				if (dbusProxy.VersionValidationEnabled)
				{
					queryParams.shell_version = dbusProxy.ShellVersion;
				}
				else
				{
					queryParams.shell_version = 'all';
				}
			}

			if ($('#search_input').val())
			{
				queryParams.search = $('#search_input').val();
                if (!queryParams.sort) {
                    hashParamUtils.setHashParam('sort', 'relevance');
                }
			}
            else
            {
                if (queryParams.sort == 'relevance') {
                    hashParamUtils.setHashParam('sort');
                }
            }

			currentRequest = $.ajax({
				url: '/extension-query/',
				dataType: 'json',
				data: queryParams,
				type: 'GET'
			}).done(function (result) {
				if ($beforePaginator)
				{
					$beforePaginator.detach();
				}
				if ($afterPaginator)
				{
					$afterPaginator.detach();
				}

				var page = parseInt(queryParams.page, 10);
				var numPages = result.numpages;

				var $paginator = paginatorUtils.buildPaginator(page, numPages, context);
				$beforePaginator = $paginator.clone().addClass('before-paginator');
				$afterPaginator = $paginator.clone().addClass('after-paginator');
				$paginator.empty();

				$.each(result.extensions, function () {
					// Serialize out the svm as we want it to be JSON
					// in the data attribute.
					this.shell_version_map = JSON.stringify(this.shell_version_map);

					if (this.description)
					{
						this.first_line_of_description = this.description.split('\n')[0];
					}
				});

				var $newContent = $(infoTemplate.render(result, {
					[infoContentsTemplate.name()]: infoContentsTemplate.template()
				}));

				$elem.removeClass('loading').empty().append($beforePaginator).append($newContent).append($afterPaginator).trigger('page-loaded');
			});
		}

		$(window).hashchange(loadPage);

		this.on('load-page', loadPage);

		return this;
	};

});
