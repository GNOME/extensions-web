/*
    GNOME Shell extensions repository
    Copyright (C) 2019  Yuri Konotopov <ykonotopov@gnome.org>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
 */

define(['mustache'], function(Mustache) {
	return {
		load: (templateFile, parentRequire, onload, config) => {
			parentRequire(['text!templates/' + templateFile + '.mst'], (loadedTemplate) => {
				onload({
					name: () => {
						return templateFile;
					},
					render: (model, partials) => {
						return Mustache.render(loadedTemplate, model, partials);
					},
					template: () => {
						return loadedTemplate
					}
				});
			});
		}
	}
});
