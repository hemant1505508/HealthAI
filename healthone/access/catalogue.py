from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .models import AccessItem, RoleProfile

DEFAULT_CATALOGUE = Path(__file__).resolve().parent.parent / "data" / "rbac_catalogue.json"


class CatalogueError(ValueError):
    """A role profile, system or permission level that the RBAC catalogue does not hold."""


@dataclass(frozen=True)
class SystemEntry:
    owner: str
    permission_levels: tuple[str, ...]


class RbacCatalogue:
    def __init__(self, systems: dict[str, SystemEntry], profiles: list[RoleProfile], additional_approver: str):
        self.systems = systems
        self.additional_approver = additional_approver
        self._profiles = {(p.job_role.casefold(), p.department.casefold()): p for p in profiles}
        for p in profiles:
            for item in p.access:
                self.check_item(item)

    @classmethod
    def load(cls, path: Path = DEFAULT_CATALOGUE) -> RbacCatalogue:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        systems = {
            name: SystemEntry(owner=s["owner"], permission_levels=tuple(s["permission_levels"]))
            for name, s in raw["systems"].items()
        }
        profiles = [RoleProfile.model_validate(p) for p in raw["role_profiles"]]
        return cls(systems, profiles, raw["additional_approver"])

    def profile(self, job_role: str, department: str) -> RoleProfile:
        """AC1: the default systems and permission levels for a job role in a department."""
        found = self._profiles.get((job_role.strip().casefold(), department.strip().casefold()))
        if found is None:
            raise CatalogueError(f"no role profile for '{job_role}' in '{department}'")
        return found

    def check_item(self, item: AccessItem) -> None:
        entry = self.systems.get(item.system)
        if entry is None:
            raise CatalogueError(f"unknown system '{item.system}'")
        if item.permission not in entry.permission_levels:
            raise CatalogueError(f"'{item.permission}' is not a permission level of {item.system}")

    def owner_of(self, system: str) -> str:
        return self.systems[system].owner
