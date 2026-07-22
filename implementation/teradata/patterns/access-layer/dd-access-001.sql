-- Access Layer — mandatory documentation record (Teradata).
-- Binding of design/patterns/access-layer.md §5. Captures the accepted role model,
-- permission boundary, and rationale inside the product so agents can read the
-- access contract at runtime. Delivered with the product's Memory documentation inserts.

INSERT INTO {ProductName}_Memory.Design_Decision
(
    decision_id, decision_version, decision_title, decision_description,
    context, alternatives_considered, rationale,
    decision_status, decision_category, source_module, module_version,
    decided_date, valid_from, valid_to, is_current
)
VALUES
(
    'DD-ACCESS-001', 1,
    'Three-tier role model for data product access control',
    'Three roles per product: {ProductName}_ROLE_READ (analysts, BI), _ROLE_AGENT
     (AI agents and automated tools), _ROLE_ADMIN (owner, steward). All consumer
     roles receive read on the module access containers. ROLE_AGENT additionally
     receives write-back on Memory (interactions, learned strategies, design
     decisions) and Observability (usage events, quality feedback). ROLE_AGENT does
     not receive write on Domain or Semantic. ROLE_ADMIN additionally reaches any
     separate base-table containers.',
    'Consumers require read on Semantic and Memory at minimum to discover and operate
     the product. Without this the product is physically deployed but operationally
     invisible to all consumers.',
    'Option 1 (chosen): three roles with separate READ and AGENT tiers. Option 2:
     single consumer role - rejected, READ and AGENT cannot then be independently
     managed or extended. Option 3: per-user grants - rejected, does not scale and
     prevents role-based revocation.',
    'Separating ROLE_AGENT from ROLE_READ enables independent lifecycle management of
     agent access and permits agent write-back to Memory and Observability without
     broadening analyst access. Domain and Semantic remain read-only for agents
     because business data and metadata are governed through controlled design and
     pipeline processes.',
    'ACCEPTED', 'SECURITY', 'ACCESS', '1.0',
    CURRENT_DATE, CURRENT_DATE, DATE '9999-12-31', 1
);
