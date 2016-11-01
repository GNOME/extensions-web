def get_model():
    from sweettooth.ratings.models import RatingComment
    return RatingComment


def get_form():
    from sweettooth.ratings.forms import RatingCommentForm
    return RatingCommentForm
