"""Authentication helpers for Bones view classes."""
from __future__ import annotations

from typing import Sequence, Tuple

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin


class BonesAuthMixin(LoginRequiredMixin, PermissionRequiredMixin):
    """Ensure Bones views require authentication and optional permissions."""

    permission_required: Sequence[str] | str | None = None
    raise_exception = False

    def get_permission_required(self) -> Tuple[str, ...]:  # type: ignore[override]
        """Return the permissions enforced for the current request."""

        perms = self.permission_required
        if perms is None:
            return ()
        if isinstance(perms, str):
            perms = (perms,)
        return tuple(perms)

    def has_permission(self) -> bool:  # type: ignore[override]
        """Allow authenticated access when no explicit permissions are required."""

        perms = self.get_permission_required()
        if not perms:
            return True
        return super().has_permission()
