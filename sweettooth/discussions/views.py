
from django.contrib import comments
from django.contrib.messages import info
from django.shortcuts import redirect

def comment_done(request):
    pk = request.GET['c']
    comment = comments.get_model().objects.get(pk=pk)
    info(request, "Thank you for your comment")
    return redirect(comment.get_content_object_url())
