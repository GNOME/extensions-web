from django.test import TestCase

from ..extensions.models import STATUS_ACTIVE, Extension, ExtensionVersion
from ..testutils import BasicUserTestCase
from .forms import RatingCommentForm


class TestRating(BasicUserTestCase, TestCase):
    def setUp(self):
        super().setUp()

        metadata = {
            "name": "Test Metadata",
            "uuid": "test-1@mecheye.net",
            "description": "Simple test metadata",
            "url": "http://test-metadata.gnome.org",
            "shell-version": ["44"],
        }

        self.extension: Extension = Extension.objects.create_from_metadata(
            metadata, creator=self.user
        )
        ExtensionVersion.objects.create(extension=self.extension, status=STATUS_ACTIVE)

        self.valid_comment_data = {
            "comment": "comment",
            "rating": 4,
        }

    def test_rating(self):
        form = RatingCommentForm(
            target_object=self.extension,
            data=self.valid_comment_data.copy() | {"rating": 6},
        )
        with self.assertRaises(ValueError):
            form.data.update(form.initial)
            form.get_comment_object()

        self.extension.refresh_from_db()
        self.assertEqual(self.extension.rated, 0)
        self.assertEqual(self.extension.rating, 0)

        form = RatingCommentForm(
            target_object=self.extension,
            data=self.valid_comment_data.copy(),
        )
        form.data.update(form.initial)
        form.get_comment_object().save()

        self.extension.refresh_from_db()
        self.assertEqual(self.extension.rated, 1)
        self.assertEqual(self.extension.rating, 4)
