"""Graph ontology for the Lex (legal) domain.

Nodes:
    Document       - a source document (contract, ruling, claim, ...)
    Clause         - a section/clause within a document
    Party          - an organization or person involved
    Obligation      - an obligation owed by one party to another
    Risk           - a potential legal/financial risk identified in a clause
    LegalNorm      - a reference to a law/article/regulation
    CourtDecision  - a court ruling that may serve as precedent
    Invoice        - a счёт на оплату (invoice) mentioned in a clause
    Deadline       - a contractual or statutory deadline (срок)
    Claim          - a legal claim / pretension (претензия)

Relationships:
    (Document)-[:CONTAINS]->(Clause)
    (Clause)-[:REGULATES]->(LegalNorm)
    (Clause)-[:VIOLATES]->(LegalNorm)
    (Clause)-[:REFERENCES]->(LegalNorm | CourtDecision)
    (CourtDecision)-[:PRECEDENT_FOR]->(Clause | Document)
    (Party)-[:OBLIGATES]->(Obligation)
    (Obligation)-[:OBLIGATES]->(Party)   # owed-to direction, see graph_rag
    (Clause)-[:HAS_RISK]->(Risk)
    (Document)-[:INVOLVES]->(Party)
    (Clause)-[:CONTAINS]->(Invoice)
    (Party)-[:ISSUES]->(Invoice)
    (Invoice)-[:BILLED_TO]->(Party)
    (Clause)-[:HAS_DEADLINE]->(Deadline)
    (Deadline)-[:BINDS]->(Party)
    (Document)-[:HAS_CLAIM]->(Claim)
    (Claim)-[:FILED_BY]->(Party)
    (Claim)-[:FILED_AGAINST]->(Party)
    (Claim)-[:REFERENCES]->(Obligation)
"""

NODE_LABELS = (
    "Document",
    "Clause",
    "Party",
    "Obligation",
    "Risk",
    "LegalNorm",
    "CourtDecision",
    "Invoice",
    "Deadline",
    "Claim",
)

RELATIONSHIP_TYPES = (
    "CONTAINS",
    "REGULATES",
    "VIOLATES",
    "REFERENCES",
    "PRECEDENT_FOR",
    "OBLIGATES",
    "HAS_RISK",
    "INVOLVES",
    "ISSUES",
    "BILLED_TO",
    "HAS_DEADLINE",
    "BINDS",
    "HAS_CLAIM",
    "FILED_BY",
    "FILED_AGAINST",
)

# Cypher statements to set up uniqueness constraints and indexes.
# Constraints implicitly create an index on the constrained property.
CONSTRAINT_STATEMENTS = (
    "CREATE CONSTRAINT document_id IF NOT EXISTS "
    "FOR (d:Document) REQUIRE d.id IS UNIQUE",

    "CREATE CONSTRAINT clause_id IF NOT EXISTS "
    "FOR (c:Clause) REQUIRE c.id IS UNIQUE",

    "CREATE CONSTRAINT party_name IF NOT EXISTS "
    "FOR (p:Party) REQUIRE p.name IS UNIQUE",

    "CREATE CONSTRAINT obligation_id IF NOT EXISTS "
    "FOR (o:Obligation) REQUIRE o.id IS UNIQUE",

    "CREATE CONSTRAINT risk_id IF NOT EXISTS "
    "FOR (r:Risk) REQUIRE r.id IS UNIQUE",

    "CREATE CONSTRAINT legal_norm_code IF NOT EXISTS "
    "FOR (n:LegalNorm) REQUIRE n.code IS UNIQUE",

    "CREATE CONSTRAINT court_decision_id IF NOT EXISTS "
    "FOR (cd:CourtDecision) REQUIRE cd.id IS UNIQUE",

    "CREATE CONSTRAINT invoice_id IF NOT EXISTS "
    "FOR (i:Invoice) REQUIRE i.id IS UNIQUE",

    "CREATE CONSTRAINT deadline_id IF NOT EXISTS "
    "FOR (d:Deadline) REQUIRE d.id IS UNIQUE",

    "CREATE CONSTRAINT claim_id IF NOT EXISTS "
    "FOR (c:Claim) REQUIRE c.id IS UNIQUE",
)

# Additional full-text indexes for search over clause/risk text.
INDEX_STATEMENTS = (
    "CREATE FULLTEXT INDEX clause_text IF NOT EXISTS "
    "FOR (c:Clause) ON EACH [c.title, c.content]",

    "CREATE FULLTEXT INDEX risk_description IF NOT EXISTS "
    "FOR (r:Risk) ON EACH [r.description]",
)


def all_setup_statements() -> tuple[str, ...]:
    """Return all Cypher statements needed to initialize the schema."""
    from core.ingestion_pipeline.tracker import JOB_CONSTRAINT
    from core.learning_brain.feedback_model import FEEDBACK_CONSTRAINT

    return CONSTRAINT_STATEMENTS + INDEX_STATEMENTS + (FEEDBACK_CONSTRAINT, JOB_CONSTRAINT)
