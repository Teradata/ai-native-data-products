"""Join groups: how an entity's `[-> Target]` attributes combine into joins.

A bare `[-> Target]` is a whole join on its own, paired with the target's identity. A named
`[-> Target.attribute]` pairs its attribute with that attribute of the target, and the named
attributes of one entity that point at the same target (and share a `[join: name]`, if any)
form one join group, in declaration order. The specification lint and the build-context
resolver both read references through this one function, so they cannot disagree.

Stdlib only.
"""
from typing import Dict, Iterable, List, Optional, Tuple

Item = Tuple[str, Optional[str], Optional[str]]  # (attribute, the `->` value, the `join` value)


def join_groups(items: Iterable[Item]) -> List[Dict]:
    """The joins declared by an entity's attributes, in declaration order.

    Each group has: `name` (the join name, else its first attribute), `target` (the entity;
    None for a multi-target reference), `targets` (every entity named), `attributes` (the
    source attributes in order), `target_attributes` (the paired target attributes, or None
    for a bare reference) and `kind`: `bare`, `named` or `multi`.
    """
    groups: List[Dict] = []
    named: Dict[Tuple[str, str], Dict] = {}
    for attribute, raw, join in items:
        if raw is None:
            continue
        targets = [t.strip() for t in raw.split("|") if t.strip()]
        if len(targets) != 1:
            groups.append({"name": attribute, "target": None, "targets": [t.partition(".")[0] for t in targets],
                           "attributes": [attribute], "target_attributes": None, "kind": "multi"})
            continue
        target, dot, target_attribute = targets[0].partition(".")
        if not dot:
            groups.append({"name": attribute, "target": target, "targets": [target], "attributes": [attribute],
                           "target_attributes": None, "kind": "bare"})
            continue
        key = (target, join or "")
        group = named.get(key)
        if group is None:
            group = {"name": join or attribute, "target": target, "targets": [target], "attributes": [],
                     "target_attributes": [], "kind": "named"}
            named[key] = group
            groups.append(group)
        group["attributes"].append(attribute)
        group["target_attributes"].append(target_attribute)
    return groups
