-- Access Layer: mandatory documentation record (Teradata).
-- Binding of the required documentation record in design/patterns/access-layer.md. Captures the accepted role model,
-- permission boundary, and rationale inside the product so agents can read the
-- access contract at runtime. Delivered with the product's Memory documentation inserts.

INSERT INTO {ProductName}_Memory.Design_Decision
(
    decision_id, decision_version, decision_title, decision_description,
    context, alternatives_considered, rationale,
    decision_status, decision_category, source_module, module_version,
    decided_date, valid_from_dts, valid_to_dts, is_current
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
    -- source_module is MEMORY, not 'ACCESS': the Access Layer is a pattern, not a
    -- module, and source_module must name a module registered in Module_Registry or
    -- the INV-MEMORY-006 join drops the row without reporting anything. Memory is
    -- the module whose grant boundary this decision defines.
    'ACCEPTED', 'SECURITY', 'MEMORY', '1.0',
    -- decided_date is a day-grain business fact and stays DATE; the validity pair
    -- is the canonical timestamp pair, with the open-end sentinel written here
    -- rather than defaulted (see 12-capture-protocol.sql.j2).
    CURRENT_DATE,
    CURRENT_TIMESTAMP(6), TIMESTAMP '9999-12-31 23:59:59.999999+00:00', 1
);
