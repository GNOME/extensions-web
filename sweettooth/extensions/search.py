
import xapian

from django.conf import settings
from django.db.models import signals

from sweettooth.extensions.models import Extension, ExtensionVersion
from sweettooth.extensions.models import reviewed, extension_updated

def index_extension(extension):
    if extension.latest_version is None:
        return

    db = xapian.WritableDatabase(settings.XAPIAN_DB_PATH, xapian.DB_CREATE_OR_OPEN)

    termgen = xapian.TermGenerator()
    termgen.set_stemmer(xapian.Stem("en"))

    doc = xapian.Document()
    termgen.set_document(doc)

    termgen.index_text(extension.name, 10)
    termgen.index_text(extension.uuid)
    termgen.index_text(extension.description)

    doc.set_data(str(extension.pk))

    idterm = "Q%s" % (extension.pk,)
    doc.add_boolean_term(idterm)
    for shell_version in extension.visible_shell_version_map.iterkeys():
        doc.add_boolean_term("V%s" % (shell_version,))

    db.replace_document(idterm, doc)

def delete_extension(extension):
    db = xapian.WritableDatabase(settings.XAPIAN_DB_PATH, xapian.DB_CREATE_OR_OPEN)
    idterm = "Q%s" % (extension.pk,)
    db.delete_document(idterm)


def reviewed_handler(sender, request, version, review, **kwargs):
    index_extension(version.extension)
reviewed.connect(reviewed_handler)

def extension_updated_handler(extension, **kwargs):
    index_extension(extension)
extension_updated.connect(extension_updated_handler)

def post_extension_delete_handler(instance, **kwargs):
    delete_extension(instance)
signals.post_delete.connect(post_extension_delete_handler, sender=Extension)

def post_version_save_handler(instance, **kwargs):
    index_extension(instance.extension)
signals.post_save.connect(post_version_save_handler, sender=ExtensionVersion)

def combine_queries(op, queries):
    def make_query(left, right):
        return xapian.Query(op, left, right)
    return reduce(make_query, queries)

def make_version_queries(versions):
    queries = [xapian.Query("V%s" % (v.version_string,)) for v in versions]
    return combine_queries(xapian.Query.OP_OR, queries)

def enquire(querystring, versions=None):
    try:
        db = xapian.Database(settings.XAPIAN_DB_PATH)
    except xapian.DatabaseOpeningError:
        return None

    qp = xapian.QueryParser()
    qp.set_stemming_strategy(qp.STEM_SOME)
    qp.set_stemmer(xapian.Stem("en"))
    qp.set_database(db)

    query = qp.parse_query(querystring, qp.FLAG_PARTIAL)

    if versions:
        query = xapian.Query(xapian.Query.OP_FILTER,
                             query,
                             make_version_queries(versions))

    enquiry = xapian.Enquire(db)
    enquiry.set_query(query)
    return db, enquiry
