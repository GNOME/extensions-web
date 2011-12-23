
from django.contrib.comments.models import Comment
from discussions import forms

def get_model():
    return Comment

def get_form():
    return forms.DiscussionCommentForm
