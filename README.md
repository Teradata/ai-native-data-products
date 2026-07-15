# AI-Native Data Product Design Standards

A comprehensive architectural framework for building AI-Native Data Products
on Teradata — modular, self-describing, and optimised for autonomous agent
discovery and operation.

---

## Overview

This repository contains the master set of design standards for AI-Native
Data Products. The standards define a six-module architecture where each
module has a distinct responsibility, its own data model, and integrates
with the others through consistent patterns.

**Design documents are the single source of truth.** The unified agent
skill (generated from these documents via the conversion prompt) is a
compressed, agent-optimised rendering of the standards — never edited
directly.

---

## Repository Structure

```
ai-native-data-products/
├── design-standards/        ← master source of truth
│   ├── AI_Native_Data_Product_Master_Design.md
│   ├── Access_Layer_Design_Standard.md
│   ├── Advocated_Data_Management_Standards.md
│   ├── Domain_Module_Design_Standard.md
│   ├── Semantic_Module_Design_Standard.md
│   ├── Search_Module_Design_Standard.md
│   ├── Prediction_Module_Design_Standard.md
│   ├── Observability_Module_Design_Standard.md
│   ├── Memory_Module_Design_Standard.md
│   ├── Temporal_Lifecycle_Metadata_Standard.md
│   └── Trust_Gate_Standard.md
│
├── platform-standards/      ← platform implementation contracts
│   ├── Object_Placement_Standard_Spec.md
│   ├── Physical_Storage_Standard_Spec.md
│   ├── Temporal_Lifecycle_Metadata_Extension.md
│   └── Trust_Gate_Extension.md
│
└── prompts/                 ← how to use the standards
    ├── Skill_Conversion_Prompt.md
    ├── Design_Data_Product_Starter.md
    ├── Access_Data_Product_Starter.md
    └── Apply_Platform_Standards.md
```

---

## The Six Modules

| Module | Purpose | Database pattern |
|--------|---------|-----------------|
| **Domain** | Core business entities — source of truth | `{Name}_Domain` |
| **Semantic** | Metadata layer enabling agent discovery | `{Name}_Semantic` |
| **Search** | Vector embeddings and similarity search | `{Name}_Search` |
| **Prediction** | Feature store and ML prediction storage | `{Name}_Prediction` |
| **Observability** | Event tracking, quality monitoring, lineage | `{Name}_Observability` |
| **Memory** | Agent state, learning, and design memory | `{Name}_Memory` |

Each module is independently deployable and composable. A data product can
implement any combination.

### Memory Module — Two Kinds of Memory

The Memory module hosts both:
- **Runtime memory** — agent sessions, interactions, learned strategies,
  user preferences, discovered patterns
- **Design memory** (Documentation Sub-Module) — architectural decisions,
  business glossary, query cookbook, change history

Both are temporal, append-oriented records of history. All documentation
tables live in `{Name}_Memory` — the data product is fully self-contained
with no external dependencies.

---

## Deployment Order

| Phase | Modules | Notes |
|-------|---------|-------|
| 1 | Memory, Semantic | Memory hosts documentation tables needed by all modules; Semantic hosts discovery metadata needed by all modules — both must exist before any other module deploys |
| 2 | Domain, Observability | Domain is the entity foundation; Observability begins monitoring Domain immediately |
| 3 | Search, Prediction | Both require Domain entities to exist first |

---

## Prompts

### Skill_Conversion_Prompt.md
Converts all design standard documents into a single unified agent skill
(`ai-native-data-product.skill`) with progressive disclosure:
- `SKILL.md` — always read by orchestrator and sub-agents; architecture,
  naming conventions, documentation capture protocol, routing instructions
- `modules/{module}.md` — read on demand; full DDL templates, design
  decisions, integration patterns, checklists for each module

Run this prompt whenever design standards are updated to regenerate the skill.

### Design_Data_Product_Starter.md
Starting prompt for designing a new data product. Directs an orchestrator
agent to load the unified skill and spin up sub-agents for each module.

### Access_Data_Product_Starter.md
Starting prompt for an agent consuming an existing data product. Guides
autonomous discovery via the Semantic module.

---

## Key Principles

1. **Design documents are the source of truth** — skills are derived,
   never edited directly
2. **Independently deployable modules** — each module is self-contained
   with its own database and data model
3. **Self-contained data products** — no cross-product database dependencies
4. **Zero data duplication** — all modules join back to Domain via foreign
   keys; Teradata co-location makes this efficient
5. **Agent-native design** — queryable metadata, standard patterns, and
   multi-hop relationship discovery enable autonomous operation
6. **Design memory** — every module records its architectural decisions into
   the Memory module's documentation tables during the design process

---

## Getting Started

### Designing a new data product

1. Review `AI_Native_Data_Product_Master_Design.md` for architecture and
   naming conventions
2. Generate the unified skill using `Skill_Conversion_Prompt.md` (attach
   all design standards; run once per framework update)
3. Use `Design_Data_Product_Starter.md` to orchestrate the design

### Updating the design standards

1. Edit the relevant design standard document(s)
2. Regenerate the unified skill using `Skill_Conversion_Prompt.md` with
   the updated document(s) and the current skill attached

---

## Design Standard Versions

| Document | Version |
|----------|---------|
| AI_Native_Data_Product_Master_Design | 1.8 |
| Domain_Module_Design_Standard | 2.3 |
| Semantic_Module_Design_Standard | 2.8 |
| Search_Module_Design_Standard | 1.5 |
| Prediction_Module_Design_Standard | 1.6 |
| Observability_Module_Design_Standard | 1.4 |
| Memory_Module_Design_Standard | 1.6 |
| Access_Layer_Design_Standard | 1.0 |
| Object_Placement_Standard_Spec | 1.0 |
| Physical_Storage_Standard_Spec | 1.0 |
| Temporal_Lifecycle_Metadata_Standard | 1.0-draft |
| Temporal_Lifecycle_Metadata_Extension (Teradata) | 1.0-draft |
| Trust_Gate_Standard | 1.0-draft |
| Trust_Gate_Extension (Teradata) | 1.0-draft |

---

## License

Copyright © 2025-2026 Teradata Corporation

Licensed under Creative Commons Attribution-NonCommercial-ShareAlike 4.0
International (CC BY-NC-SA 4.0). See [LICENSE.md](LICENSE.md) for full terms.

---

## Acknowledgments

Developed by Teradata's Worldwide Data Architecture Team,
Field Technology Organization.

---

**Last Updated**: March 2026  
**Status**: Active Development — documentation-memory-merge branch
