"""Policy Engine - Evaluates policies and makes authorization decisions.

The engine loads terms and relations, and evaluates decision requests against the policy graph.
"""

import copy
import hashlib
import json
import threading
from enum import Enum
from functools import wraps
from typing import Any, Dict, List, Optional

from lexecon.policy.relations import PolicyRelation, RelationType
from lexecon.policy.terms import PolicyTerm


class PolicyVersionConflict(ValueError):
    """The active policy changed since the caller took its snapshot."""


def _synchronized(method):
    """Serialize supported policy reads and mutations on the same engine."""
    @wraps(method)
    def locked(self, *args, **kwargs):
        with self._policy_lock:
            return method(self, *args, **kwargs)
    return locked


class PolicyDecision:
    """Represents a policy evaluation decision."""

    def __init__(self, allowed: bool, reason: str, **kwargs: Any) -> None:
        self.allowed = allowed
        self.reason = reason
        self.policy_version_hash: str = kwargs.get("policy_version_hash", "")
        self.permitted = allowed  # Backwards compatibility
        self.reasoning = reason  # Backwards compatibility
        self._extra = kwargs
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __getitem__(self, key: str) -> Any:
        """Support dictionary-style access for backwards compatibility."""
        if key == "permitted":
            return self.permitted
        if key == "allowed":
            return self.allowed
        if key == "reason":
            return self.reason
        if key == "reasoning":
            return self.reasoning
        if hasattr(self, key):
            return getattr(self, key)
        if key in self._extra:
            return self._extra[key]
        raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        """Support dict.get() for backwards compatibility."""
        try:
            return self[key]
        except KeyError:
            return default


class PolicyMode(Enum):
    """Policy evaluation modes."""

    PERMISSIVE = "permissive"  # Allow unless explicitly forbidden
    STRICT = "strict"  # Deny unless explicitly permitted
    PARANOID = "paranoid"  # Deny high risk unless human confirmation


class PolicyEngine:
    """Policy engine for evaluating governance decisions.

    Maintains the policy graph (terms + relations) and evaluates requests.
    """

    def __init__(self, mode: Any = PolicyMode.STRICT) -> None:
        self._policy_lock = threading.RLock()
        self.terms: Dict[str, PolicyTerm] = {}
        self.relations: List[PolicyRelation] = []
        self._policy_hash: Optional[str] = None
        # Handle both string and PolicyMode enum inputs, or a full policy dict
        if isinstance(mode, dict):
            # If passed a policy dict, extract the mode and load the policy
            policy_dict = mode
            mode_value = policy_dict.get("mode", "strict")
            if isinstance(mode_value, str):
                self.mode = PolicyMode(mode_value)
            else:
                self.mode = mode_value
            # Load the policy
            self.load_policy(policy_dict)
        else:
            # Normal mode initialization
            if isinstance(mode, str):
                self.mode = PolicyMode(mode)
            elif isinstance(mode, PolicyMode):
                self.mode = mode
            else:
                self.mode = PolicyMode.STRICT

    @_synchronized
    def add_term(self, term: PolicyTerm) -> None:
        """Add a policy term to the engine."""
        self.terms[term.term_id] = copy.deepcopy(term)
        self._policy_hash = None  # Invalidate cached hash

    @_synchronized
    def add_relation(self, relation: PolicyRelation) -> None:
        """Add a policy relation to the engine."""
        self.relations.append(copy.deepcopy(relation))
        self._policy_hash = None  # Invalidate cached hash

    @_synchronized
    def load_policy(
        self, policy_data: Dict[str, Any], expected_policy_hash: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Replace policy, optionally only if its current hash matches the caller.

        Omitted mode preserves the current mode. Supplied mode is part of the
        replacement so exported snapshots can restore all active semantics.
        The returned detached snapshot describes this mutation even if another
        writer changes the engine immediately afterward.
        """
        previous_policy_hash = self.get_policy_hash()
        if expected_policy_hash is not None and expected_policy_hash != previous_policy_hash:
            raise PolicyVersionConflict("Active policy changed; export it again before replacing")
        # Parse and serialize everything before touching live authorization state.
        # Copy nested metadata/conditions so caller mutation cannot evade the lock.
        candidate = copy.deepcopy(policy_data)
        mode = PolicyMode(candidate.get("mode", self.mode.value))
        terms = [PolicyTerm.from_dict(item) for item in candidate.get("terms", [])]
        relations = [PolicyRelation.from_dict(item) for item in candidate.get("relations", [])]
        term_map = {term.term_id: term for term in terms}
        policy = {
            "mode": mode.value,
            "terms": [term.to_dict() for term in term_map.values()],
            "relations": [relation.to_dict() for relation in relations],
        }
        encoded = json.dumps(policy, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        policy_hash = hashlib.sha256(encoded).hexdigest()
        self.mode = mode
        self.terms = term_map
        self.relations = relations
        self._policy_hash = policy_hash
        return {"policy": copy.deepcopy(policy), "policy_hash": policy_hash, "previous_policy_hash": previous_policy_hash}

    @_synchronized
    def export_policy(self) -> Dict[str, Any]:
        """Return a detached, restorable policy and its matching version hash."""
        return {"policy": self.to_dict(), "policy_hash": self.get_policy_hash()}

    @_synchronized
    def get_policy_hash(self) -> str:
        """Get deterministic hash of current policy version.

        Uses canonical JSON serialization for stable hashing.
        """
        if self._policy_hash is not None:
            return self._policy_hash

        policy_dict = self.to_dict()
        canonical_json = json.dumps(policy_dict, sort_keys=True, separators=(",", ":"))
        self._policy_hash = hashlib.sha256(canonical_json.encode()).hexdigest()
        return self._policy_hash

    @_synchronized
    def evaluate(
        self,
        actor: str,
        action: str,
        resource: Optional[str] = None,
        data_classes: Optional[List[str]] = None,
        risk_level: int = 1,
        context: Optional[Dict[str, Any]] = None,
    ) -> PolicyDecision:
        """Evaluate a decision request against the policy.

        Returns a decision with permitted/denied status and reasoning.
        """
        if data_classes is None:
            data_classes = []
        if context is None:
            context = {}

        # Find relevant relations
        permits = self._find_relations(RelationType.PERMITS, actor, action, data_classes, context)
        forbids = self._find_relations(RelationType.FORBIDS, actor, action, data_classes, context)

        # Evaluate based on mode
        if self.mode == PolicyMode.STRICT:
            # Deny unless explicitly permitted
            decision = len(permits) > 0 and len(forbids) == 0
        elif self.mode == PolicyMode.PERMISSIVE:
            # Allow unless explicitly forbidden
            decision = len(forbids) == 0
        else:  # PARANOID
            # Caller context cannot attest human approval; high-risk requests
            # need a separate authenticated oversight workflow.
            decision = risk_level < 4 and len(permits) > 0 and len(forbids) == 0

        reasoning = self._generate_reasoning(decision, permits, forbids)
        return PolicyDecision(
            allowed=decision,
            reason=reasoning,
            mode=self.mode.value,
            permits_count=len(permits),
            forbids_count=len(forbids),
            policy_version_hash=self.get_policy_hash(),
        )

    def _find_relations(
        self, relation_type: RelationType, actor: str, action: str,
        data_classes: Optional[List[str]] = None, context: Optional[Dict[str, Any]] = None,
    ) -> List[PolicyRelation]:
        """Find relations matching the given criteria.

        Matches by both term ID and term label/name.
        Also checks data_classes against the relation's object field if present.
        """
        if data_classes is None:
            data_classes = []

        matching = []
        for relation in self.relations:
            if relation.relation_type != relation_type:
                continue

            # Check if actor matches the source term
            actor_matches = self._term_matches(actor, relation.source)
            # Check if action matches the target term
            action_matches = self._term_matches(action, relation.target)

            # Check if data_class matches the object field (if present)
            object_matches = True  # Default to true if no object specified
            if "object" in relation.metadata:
                # If relation has an object field, at least one data_class must match
                if data_classes:
                    object_matches = any(
                        self._term_matches(dc, relation.metadata["object"]) for dc in data_classes
                    )
                else:
                    # Relation specifies an object but no data_classes provided - no match
                    object_matches = False

            # Only explicit boolean context flags are supported. Unknown
            # conditions cannot grant access; conditional forbids remain active.
            conditions = relation.conditions or []
            if relation.metadata.get("condition"):
                conditions = [*conditions, relation.metadata["condition"]]
            conditions_met = all((context or {}).get(item) is True for item in conditions)
            if actor_matches and action_matches and object_matches and (
                conditions_met or relation_type == RelationType.FORBIDS
            ):
                matching.append(relation)
        return matching

    def _term_matches(self, value: str, term_id: str) -> bool:
        """Check if a value matches a term by ID or label.

        Args:
            value: The value to match (e.g., "model" or "actor:model")
            term_id: The term ID to match against (e.g., "actor:model")

        Returns:
            True if value matches the term ID or the term's label
        """
        # Exact match with term ID
        if value == term_id:
            return True

        # Check if the value matches the term's label
        term = self.terms.get(term_id)
        if term and term.label == value:
            return True

        # Permit a short, exact name for a typed ID ("model" -> "actor:model")
        # without treating partial attacker strings as matches.
        return bool(value) and ":" in term_id and value == term_id.split(":", 1)[1]

    def _generate_reasoning(
        self, decision: bool, permits: List[PolicyRelation], forbids: List[PolicyRelation],
    ) -> str:
        """Generate human-readable reasoning for the decision."""
        if decision:
            reasons = []
            for permit in permits[:3]:  # Show up to 3 reasons
                if "justification" in permit.metadata:
                    reasons.append(permit.metadata["justification"])
            if reasons:
                return f"Permitted: {'; '.join(reasons)}"
            return f"Permitted by {len(permits)} rule(s), no conflicts"
        if len(forbids) > 0:
            reasons = []
            for forbid in forbids[:3]:  # Show up to 3 reasons
                if "justification" in forbid.metadata:
                    reasons.append(forbid.metadata["justification"])
            if reasons:
                return f"Denied: {'; '.join(reasons)}"
            return f"Denied by {len(forbids)} prohibition(s)"
        return "Action not explicitly permitted"

    @_synchronized
    def to_dict(self) -> Dict[str, Any]:
        """Serialize policy to dictionary."""
        return copy.deepcopy({
            "mode": self.mode.value,
            "terms": [term.to_dict() for term in self.terms.values()],
            "relations": [relation.to_dict() for relation in self.relations],
        })

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PolicyEngine":
        """Deserialize policy from dictionary."""
        engine = cls(mode=PolicyMode(data.get("mode", "strict")))
        engine.load_policy(data)
        return engine
