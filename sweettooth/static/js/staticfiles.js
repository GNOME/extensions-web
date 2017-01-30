/*
    GNOME Shell extensions repository
    Copyright (C) 2017  Yuri Konotopov <ykonotopov@gnome.org>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
 */

define(function() {
	"use strict";

	return {
		getImage: function(path) {
			if(!django_static_images || !django_static_images[path])
			{
				return;
			}

			return django_static_images[path];
		},

		getImageFile: function(path) {
			let image = this.getImage(path);

			if(image)
			{
				image = image.split('/');
				return image[image.length - 1];
			}

			return image;
		}
	}
});
