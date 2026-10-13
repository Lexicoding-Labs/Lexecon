"""Evidence Export Service - Generates compliance-ready export bundles.

Creates ZIP archives containing:
- ledger_events.json
- verification_report.json
- policies.json
- summary.md
- manifest.json (signed)
"""

import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone
from typing import Dict, List, Optional

from lexecon.ledger.chain import LedgerChain
from lexecon.security.signature_service import SignatureService


class EvidenceBundle:
    """Represents an evidence export bundle."""

    def __init__(
        self,
        tenant_id: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        ledger_entries: Optional[List[Dict]] = None,
        verification_report: Optional[Dict] = None,
        policies: Optional[List[Dict]] = None,
    ):
        self.tenant_id = tenant_id
        self.start_time = start_time
        self.end_time = end_time
        self.ledger_entries = ledger_entries or []
        self.verification_report = verification_report or {}
        self.policies = policies or []
        self.exported_at = datetime.now(timezone.utc).isoformat()

    def to_zip_bytes(self, signature_service: Optional[SignatureService] = None) -> bytes:
        """Generate ZIP archive as bytes."""
        buffer = io.BytesIO()
        
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            files_manifest = []
            
            # 1. ledger_events.json
            ledger_content = self._generate_ledger_events_json()
            zf.writestr('ledger_events.json', ledger_content)
            files_manifest.append({
                'path': 'ledger_events.json',
                'sha256': hashlib.sha256(ledger_content.encode()).hexdigest()
            })
            
            # 2. verification_report.json
            verification_content = self._generate_verification_report_json()
            zf.writestr('verification_report.json', verification_content)
            files_manifest.append({
                'path': 'verification_report.json',
                'sha256': hashlib.sha256(verification_content.encode()).hexdigest()
            })
            
            # 3. policies.json
            policies_content = self._generate_policies_json()
            zf.writestr('policies.json', policies_content)
            files_manifest.append({
                'path': 'policies.json',
                'sha256': hashlib.sha256(policies_content.encode()).hexdigest()
            })
            
            # 4. summary.md
            summary_content = self._generate_summary_md()
            zf.writestr('summary.md', summary_content)
            files_manifest.append({
                'path': 'summary.md',
                'sha256': hashlib.sha256(summary_content.encode()).hexdigest()
            })
            
            # 5. manifest.json (signed)
            manifest_content = self._generate_manifest_json(files_manifest, signature_service)
            zf.writestr('manifest.json', manifest_content)
        
        buffer.seek(0)
        return buffer.read()

    def _generate_ledger_events_json(self) -> str:
        """Generate ledger_events.json content."""
        events = []
        for entry in self.ledger_entries:
            events.append({
                'entry_id': entry.get('entry_id'),
                'event_type': entry.get('event_type'),
                'timestamp': entry.get('timestamp'),
                'previous_hash': entry.get('previous_hash'),
                'entry_hash': entry.get('entry_hash'),
                # Every data field participates in the source entry hash.
                'data': entry.get('data', {}),
            })
        
        payload = {
            'tenant_id': self.tenant_id,
            'exported_at': self.exported_at,
            'time_range': {
                'start': self.start_time,
                'end': self.end_time,
            },
            'events': events,
        }
        return json.dumps(payload, indent=2, default=str)

    def _generate_verification_report_json(self) -> str:
        """Generate verification_report.json content."""
        report = self.verification_report or {}
        
        payload = {
            'tenant_id': self.tenant_id,
            'exported_at': self.exported_at,
            'verified': report.get('valid'),
            'checked_count': report.get('entries_checked', 0),
            'failed_count': report.get('entries_checked', 0) - report.get('entries_verified', 0),
            'failures': [],
            'scope': 'source_chain_and_exported_entry_hashes' if report else 'unchecked',
            'source_chain_valid': report.get('source_chain_valid') if report else None,
            'exported_subset': True,
            'method': {
                'chain_verification': bool(report),
                'hash_algorithm': 'sha256',
                'entry_hash_field': 'entry_hash',
                'previous_hash_field': 'previous_hash',
            },
        }
        return json.dumps(payload, indent=2)

    def _generate_policies_json(self) -> str:
        """Generate policies.json content."""
        # Extract unique policy hashes from ledger entries
        policy_hashes = set()
        for entry in self.ledger_entries:
            data = entry.get('data', {})
            if data.get('policy_version_hash'):
                policy_hashes.add(data['policy_version_hash'])
        
        policy_versions = [
            {
                'policy_version_hash': h,
                'policy_id': None,
                'name': None,
            }
            for h in sorted(policy_hashes)
        ]
        
        payload = {
            'tenant_id': self.tenant_id,
            'exported_at': self.exported_at,
            'policy_versions': policy_versions,
        }
        return json.dumps(payload, indent=2)

    def _generate_summary_md(self) -> str:
        """Generate human-readable summary.md."""
        # Calculate stats
        total = len(self.ledger_entries)
        decisions = [e for e in self.ledger_entries if e.get('event_type') == 'decision']
        
        outcomes: Dict[str, int] = {}
        actions: Dict[str, int] = {}
        risk_levels: Dict[str, int] = {}
        
        for entry in decisions:
            data = entry.get('data', {})
            # Outcome
            outcome = data.get('decision', 'unknown')
            outcomes[outcome] = outcomes.get(outcome, 0) + 1
            # Action
            action = data.get('action', 'unknown')
            actions[action] = actions.get(action, 0) + 1
            # Risk level
            risk = self._risk_label(data.get('risk_level'))
            risk_levels[risk] = risk_levels.get(risk, 0) + 1
        
        # Policy hashes
        policy_hashes = set()
        for entry in self.ledger_entries:
            data = entry.get('data', {})
            if data.get('policy_version_hash'):
                policy_hashes.add(data['policy_version_hash'][:16] + '...')

        verification_status = (
            'UNCHECKED' if not self.verification_report else
            ('PASSED (source chain and exported entry hashes)'
             if self.verification_report.get('valid') else 'FAILED')
        )
        
        md = f"""# Lexecon Evidence Export Summary

**Tenant:** {self.tenant_id}  
**Exported:** {self.exported_at}  
**Time Range:** {self.start_time or 'All time'} to {self.end_time or 'Now'}

---

## Summary Statistics

| Metric | Value |
|--------|-------|
| Total Ledger Entries | {total} |
| Decision Events | {len(decisions)} |
| Verification Status | {verification_status} |

---

## Outcome Distribution

| Outcome | Count | Percentage |
|---------|-------|------------|
"""
        for outcome, count in sorted(outcomes.items()):
            pct = (count / len(decisions) * 100) if decisions else 0
            md += f"| {outcome.upper()} | {count} | {pct:.1f}% |\n"
        
        md += """
---

## Top Actions

| Action | Count |
|--------|-------|
"""
        for action, count in sorted(actions.items(), key=lambda x: -x[1])[:10]:
            md += f"| {action} | {count} |\n"
        
        md += """
---

## Risk Level Distribution

| Risk Level | Count |
|------------|-------|
"""
        for risk, count in sorted(risk_levels.items()):
            md += f"| {risk.upper()} | {count} |\n"
        
        md += """
---

## Policy Versions Referenced

"""
        for h in sorted(policy_hashes):
            md += f"- `{h}`\n"
        
        md += """
---

## Files in This Bundle

- `ledger_events.json` - Selected tenant entries with their complete hash inputs
- `verification_report.json` - Chain integrity verification results
- `policies.json` - Policy version references
- `summary.md` - This human-readable summary
- `manifest.json` - Signed manifest with file integrity hashes

---

## Verification

This bundle was generated by Lexecon AI Governance Platform.
Exported entries include SHA-256 hashes and the previous hash from the source
ledger. This subset omits other entries, so it cannot independently prove full
source-chain continuity. When enabled, the source chain is checked before
export and each included entry hash is checked.

To verify independently:
1. Check each entry's `entry_hash` matches SHA-256 of its content
2. Obtain the full source chain to verify every `previous_hash` link
3. Validate the signature in `manifest.json`

---

*Generated by Lexecon v0.1.0*  
*Prototype evidence export; no regulatory compliance claim*
"""
        return md

    @staticmethod
    def _risk_label(value: object) -> str:
        """Use the same 1–5 display buckets as the dashboard for mixed ledgers."""
        numeric = {1: 'low', 2: 'medium', 3: 'high', 4: 'critical', 5: 'critical'}
        if type(value) is int:
            return numeric.get(value, 'unknown')
        if isinstance(value, str):
            label = value.strip().lower()
            if label.isdecimal():
                return numeric.get(int(label), 'unknown')
            if label in {'minimal', 'low', 'medium', 'high', 'critical'}:
                return label
        return 'unknown'

    def _generate_manifest_json(
        self, files: List[Dict], signature_service: Optional[SignatureService] = None,
    ) -> str:
        """Generate signed manifest.json."""
        # Compute bundle hash (hash of concatenated file hashes)
        file_hashes = ''.join(f['sha256'] for f in sorted(files, key=lambda x: x['path']))
        bundle_hash = hashlib.sha256(file_hashes.encode()).hexdigest()
        
        # Sign the exact bundle hash using the service's supported API. A
        # configured signer failure must not silently produce an unsigned ZIP.
        signature = signature_service.sign_packet({'bundle_hash': bundle_hash}) if signature_service else None
        
        manifest = {
            'tenant_id': self.tenant_id,
            'exported_at': self.exported_at,
            'bundle_files': files,
            'bundle_hash': bundle_hash,
            'signature': signature,
            'signing_key_id': 'lexecon_root_001' if signature else None,
            'format_version': '1.0.0',
        }
        return json.dumps(manifest, indent=2)


class EvidenceExportService:
    """Service for generating evidence export bundles."""

    def __init__(
        self, ledger: LedgerChain, signature_service: Optional[SignatureService] = None,
    ) -> None:
        self.ledger = ledger
        self.signature_service = signature_service

    def export(
        self,
        tenant_id: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 1000,
        include_verification: bool = True,
    ) -> bytes:
        """Generate evidence export bundle as ZIP bytes."""
        # Filter entries by time range
        entries = self._filter_entries(tenant_id, start_time, end_time, limit)
        
        # Get verification report
        verification_report = {}
        if include_verification and self.ledger:
            source_check = self.ledger.verify_integrity()
            entries_verified = sum(
                entry['entry_hash'] == hashlib.sha256(json.dumps(
                    {key: entry[key] for key in ('entry_id', 'event_type', 'data', 'timestamp', 'previous_hash')},
                    sort_keys=True, separators=(',', ':'),
                ).encode()).hexdigest()
                for entry in entries
            )
            verification_report = {
                'valid': bool(source_check.get('valid')) and entries_verified == len(entries),
                'entries_checked': len(entries),
                'entries_verified': entries_verified,
                'source_chain_valid': bool(source_check.get('valid')),
            }
        
        # Create bundle
        bundle = EvidenceBundle(
            tenant_id=tenant_id,
            start_time=start_time,
            end_time=end_time,
            ledger_entries=entries,
            verification_report=verification_report,
        )
        
        return bundle.to_zip_bytes(self.signature_service)

    def _filter_entries(
        self,
        tenant_id: str,
        start_time: Optional[str],
        end_time: Optional[str],
        limit: int,
    ) -> List[Dict]:
        """Filter ledger entries by time range."""
        entries: List[Dict] = []
        
        for entry in reversed(self.ledger.entries):  # Most recent first
            entry_dict = entry.to_dict()
            if entry_dict.get('data', {}).get('tenant_id') != tenant_id:
                continue
            
            # Time filtering (simple string comparison works for ISO format)
            ts = entry_dict.get('timestamp', '')
            if start_time and ts < start_time:
                continue
            if end_time and ts > end_time:
                continue
            
            entries.append(entry_dict)
            if len(entries) >= limit:
                break
        
        return entries
