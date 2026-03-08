from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(slots=True)
class FileReport:
    relative_path: str
    action: str
    masker: str
    stats: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class RunReport:
    run_id: str
    source_root: str
    output_root: str
    mapping_file: str
    files: list[FileReport] = field(default_factory=list)
    totals: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "source_root": self.source_root,
            "output_root": self.output_root,
            "mapping_file": self.mapping_file,
            "files": [item.to_dict() for item in self.files],
            "totals": dict(self.totals),
        }
