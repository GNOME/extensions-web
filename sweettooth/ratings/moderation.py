from django_comments.moderation import CommentModerator


class ExtensionCommentsModerator(CommentModerator):
    email_notification = False
    enable_field = "allow_comments"
