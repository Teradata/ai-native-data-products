---
title: PostgreSQL Access Layer Implementation
anchor: access-layer
type: implementation
status: draft
version: 2.0
normative: true
implements: access-layer
platform: postgres
---

# PostgreSQL: Access Layer

Binding of [Access Layer](../../../../design/patterns/access-layer.md). The design owns the contract; this binding adds platform mechanisms and enforcement limits.

[grants.sql](grants.sql) creates independent NOLOGIN READ, AGENT and ADMIN group roles. Deployment requires CREATEROLE, schema creation and permission to install `btree_gist`. Object ownership stays with the deploying maintainer. Grant membership to real logins separately; no passwords or LOGIN accounts are shipped.

READ and AGENT get SELECT only on registered approved views. AGENT also gets scoped runtime SELECT/INSERT/UPDATE and append-only outcome INSERT. ADMIN gets maintenance DML, sequences and function execution; ownership/DDL remains with the deployer. PUBLIC loses product schema, table and function access. Default function execution is revoked for future functions created by that deployer; future objects need reviewed grants.

RLS permits USER rows only when scope_identifier equals session_user. This identifies the authenticated login even after SET ROLE. Shared scope membership is not implemented. Owners, superusers and BYPASSRLS roles remain trusted administration; never grant them to consumers. Historical functions are ADMIN-only; approved search functions are invoker-rights and query approved views.

Integration tests verify view access, denied base/history/runtime reads for READ, denied outcome updates and scope spoofing. The operational access-layer area remains unknown until login provisioning and membership are reviewed. These SQL policies alone do not assess network authentication or pooled application identities.
