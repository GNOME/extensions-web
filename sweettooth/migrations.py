from collections.abc import Sequence
from typing import Any

from django.db.migrations import RunSQL


class VendorAwareRunSQL(RunSQL):
    def __init__(
        self,
        database_vendors: str | Sequence[str],
        sql,
        reverse_sql=None,
        state_operations=None,
        hints=None,
        elidable=False,
    ):
        super().__init__(sql, reverse_sql, state_operations, hints, elidable)

        if isinstance(database_vendors, str):
            database_vendors = [database_vendors]

        self._vendors = database_vendors

    def _vendor_allowed(self, vendor: str):
        return any(v in vendor.lower() for v in self._vendors)

    def database_forwards(
        self, app_label: Any, schema_editor: Any, from_state: Any, to_state: Any
    ) -> None:
        if self._vendor_allowed(schema_editor.connection.vendor):
            return super().database_forwards(
                app_label, schema_editor, from_state, to_state
            )

    def database_backwards(
        self, app_label: Any, schema_editor: Any, from_state: Any, to_state: Any
    ) -> None:
        if self._vendor_allowed(schema_editor.connection.vendor):
            return super().database_backwards(
                app_label, schema_editor, from_state, to_state
            )
