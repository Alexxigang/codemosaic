from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AuditEvent:
    event_time: str
    action: str
    workspace_root: str
    details: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            'event_time': self.event_time,
            'action': self.action,
            'workspace_root': self.workspace_root,
            'details': dict(self.details),
        }



def default_audit_log_path(workspace_root: Path) -> Path:
    return workspace_root / '.codemosaic' / 'audit-log.jsonl'



def append_audit_event(workspace_root: Path, action: str, **details: object) -> Path:
    log_path = default_audit_log_path(workspace_root.resolve())
    log_path.parent.mkdir(parents=True, exist_ok=True)
    payload = AuditEvent(
        event_time=datetime.now().isoformat(timespec='seconds'),
        action=action,
        workspace_root=str(workspace_root.resolve()),
        details=_sanitize_details(details),
    ).to_dict()
    with log_path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + '\n')
    return log_path



def read_audit_events(workspace_root: Path, *, limit: int | None = None) -> list[dict[str, object]]:
    log_path = default_audit_log_path(workspace_root.resolve())
    if not log_path.exists():
        return []
    events: list[dict[str, object]] = []
    for line in log_path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            events.append(payload)
    if limit is not None:
        return events[-limit:][::-1]
    return list(reversed(events))



def _sanitize_details(details: dict[str, object]) -> dict[str, object]:
    payload: dict[str, object] = {}
    for key, value in details.items():
        if value in (None, '', [], {}):
            continue
        if isinstance(value, Path):
            payload[key] = str(value)
        elif isinstance(value, dict):
            payload[key] = _sanitize_details(value)
        elif isinstance(value, (list, tuple)):
            payload[key] = [str(item) if isinstance(item, Path) else item for item in value]
        else:
            payload[key] = value
    return payload
