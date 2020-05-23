
from django.core.management.base import BaseCommand, make_option
from sweettooth.extensions.models import Extension
from sweettooth.extensions.search import enquire

def append_version(option, opt_str, value, parser):
    values = parser.values
    if getattr(values, "versions", None) is None:
        values.versions = []
    values.versions.append(value)

class Command(BaseCommand):
    args = '<query>'
    help = 'Test the search engine'

    option_list = BaseCommand.option_list + (
        make_option('-V', action="callback", callback=append_version, type="string"),
    )

    def handle(self, *args, **kwargs):
        query = ' '.join(args)
        versions = kwargs.get('versions')
        db, enquiry = enquire(query, versions)

        mset = enquiry.get_mset(0, db.get_doccount())
        pks = [match.document.get_data() for match in mset]

        # filter doesn't guarantee an order, so we need to get all the
        # possible models then look them up to get the ordering
        # returned by xapian. This hits the database all at once, rather
        # than pagesize times.
        extension_lookup = {}
        for extension in Extension.objects.filter(pk__in=pks):
            extension_lookup[str(extension.pk)] = extension

        extensions = [extension_lookup[pk] for pk in pks]
        for ext in extensions:
            print(ext.name)
