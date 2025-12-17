-- PSP Reconciliation Platform - Initial Database Schema
-- PostgreSQL 15+
-- Multi-tenant with row-level security

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================================
-- TENANT HIERARCHY
-- ============================================================================

CREATE TABLE tenant (
    tenant_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_name VARCHAR(255) NOT NULL,
    tenant_code VARCHAR(50) UNIQUE NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE brand (
    brand_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenant(tenant_id) ON DELETE CASCADE,
    brand_name VARCHAR(255) NOT NULL,
    brand_code VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, brand_code)
);

CREATE TABLE entity (
    entity_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    brand_id UUID NOT NULL REFERENCES brand(brand_id) ON DELETE CASCADE,
    entity_name VARCHAR(255) NOT NULL,
    entity_code VARCHAR(50) NOT NULL,
    jurisdiction VARCHAR(100),
    base_currency VARCHAR(3) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(brand_id, entity_code)
);

CREATE TABLE psp_connection (
    psp_connection_id VARCHAR(100) PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenant(tenant_id) ON DELETE CASCADE,
    entity_id UUID REFERENCES entity(entity_id),
    psp_name VARCHAR(100) NOT NULL,
    connector_type VARCHAR(50) NOT NULL, -- WEBHOOK, API_POLLING, SFTP, EMAIL, MANUAL
    endpoint_url TEXT,
    authentication_type VARCHAR(50), -- API_KEY, OAUTH2, BASIC
    authentication_secret_arn TEXT, -- AWS Secrets Manager ARN
    webhook_signature_secret_arn TEXT,
    parser_version VARCHAR(50),
    schema_version INTEGER DEFAULT 1,
    enabled BOOLEAN NOT NULL DEFAULT true,
    config JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- RAW EVENTS (Metadata - actual data in S3)
-- ============================================================================

CREATE TABLE raw_event_metadata (
    raw_event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenant(tenant_id) ON DELETE CASCADE,
    psp_connection_id VARCHAR(100) NOT NULL REFERENCES psp_connection(psp_connection_id),
    source_type VARCHAR(50) NOT NULL, -- WEBHOOK, API, SFTP, EMAIL, MANUAL
    s3_path TEXT NOT NULL,
    file_name VARCHAR(255),
    file_size BIGINT,
    content_type VARCHAR(100),
    idempotency_key VARCHAR(255) NOT NULL,
    ingestion_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processing_status VARCHAR(50) NOT NULL DEFAULT 'PENDING', -- PENDING, PROCESSED, FAILED
    error_message TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_raw_event_idempotency 
    ON raw_event_metadata(tenant_id, idempotency_key);

-- ============================================================================
-- NORMALIZED TRANSACTIONS
-- ============================================================================

CREATE TABLE normalized_transaction (
    transaction_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenant(tenant_id) ON DELETE CASCADE,
    brand_id UUID NOT NULL REFERENCES brand(brand_id) ON DELETE CASCADE,
    entity_id UUID NOT NULL REFERENCES entity(entity_id) ON DELETE CASCADE,
    psp_connection_id VARCHAR(100) NOT NULL REFERENCES psp_connection(psp_connection_id),
    event_type VARCHAR(50) NOT NULL, -- DEPOSIT, WITHDRAWAL, REFUND, CHARGEBACK, etc.
    event_timestamp TIMESTAMPTZ NOT NULL,
    transaction_date DATE NOT NULL,
    amount_value BIGINT NOT NULL, -- stored in cents/smallest unit
    amount_currency VARCHAR(3) NOT NULL,
    amount_original_currency VARCHAR(3),
    amount_fx_rate NUMERIC(10, 6),
    amount_fx_rate_source VARCHAR(50),
    amount_fx_rate_date DATE,
    psp_transaction_id VARCHAR(255) NOT NULL,
    psp_payment_id VARCHAR(255),
    psp_settlement_id VARCHAR(255),
    psp_batch_id VARCHAR(255),
    customer_id VARCHAR(255),
    player_id VARCHAR(255),
    game_session_id VARCHAR(255),
    psp_fee BIGINT, -- cents
    fx_fee BIGINT, -- cents
    net_amount BIGINT, -- cents
    status VARCHAR(50) NOT NULL, -- COMPLETED, PENDING, FAILED, CANCELLED
    reconciliation_status VARCHAR(50) NOT NULL DEFAULT 'PENDING', -- PENDING, MATCHED, PARTIAL_MATCH, UNMATCHED, EXPECTED, POSTED, VOIDED
    source_type VARCHAR(50) NOT NULL,
    source_idempotency_key VARCHAR(255) NOT NULL,
    source_raw_event_id UUID REFERENCES raw_event_metadata(raw_event_id),
    source_raw_event_s3_path TEXT,
    metadata JSONB, -- flexible schema for PSP-specific data
    version INTEGER NOT NULL DEFAULT 1,
    schema_version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (transaction_date);

-- Indexes for normalized_transaction
CREATE INDEX idx_normalized_transaction_tenant_date 
    ON normalized_transaction (tenant_id, transaction_date);
CREATE INDEX idx_normalized_transaction_psp_ref 
    ON normalized_transaction (psp_connection_id, psp_transaction_id, event_type);
CREATE INDEX idx_normalized_transaction_reconciliation_status 
    ON normalized_transaction (tenant_id, reconciliation_status, transaction_date);
CREATE UNIQUE INDEX idx_normalized_transaction_idempotency 
    ON normalized_transaction (tenant_id, psp_connection_id, psp_transaction_id, event_type);
CREATE INDEX idx_normalized_transaction_entity_date 
    ON normalized_transaction (entity_id, transaction_date);

-- Create partition for current month (example: January 2024)
CREATE TABLE normalized_transaction_2024_01 
    PARTITION OF normalized_transaction
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- ============================================================================
-- PSP SETTLEMENTS
-- ============================================================================

CREATE TABLE psp_settlement (
    settlement_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenant(tenant_id) ON DELETE CASCADE,
    psp_connection_id VARCHAR(100) NOT NULL REFERENCES psp_connection(psp_connection_id),
    settlement_date DATE NOT NULL,
    settlement_batch_id VARCHAR(255) NOT NULL,
    settlement_line_number INTEGER NOT NULL,
    amount_value BIGINT NOT NULL, -- cents
    amount_currency VARCHAR(3) NOT NULL,
    psp_settlement_id VARCHAR(255),
    psp_transaction_ids TEXT[], -- array of transaction IDs
    psp_fee BIGINT, -- cents
    net_amount BIGINT, -- cents
    source_file_path TEXT,
    source_parser_version VARCHAR(50),
    source_ingestion_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, psp_connection_id, settlement_date, settlement_batch_id, settlement_line_number)
) PARTITION BY RANGE (settlement_date);

CREATE INDEX idx_psp_settlement_tenant_date 
    ON psp_settlement (tenant_id, settlement_date);
CREATE INDEX idx_psp_settlement_psp_date 
    ON psp_settlement (psp_connection_id, settlement_date);
CREATE INDEX idx_psp_settlement_batch 
    ON psp_settlement (psp_connection_id, settlement_batch_id);

-- Create partition for current month
CREATE TABLE psp_settlement_2024_01 
    PARTITION OF psp_settlement
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- ============================================================================
-- RECONCILIATION MATCHES
-- ============================================================================

CREATE TABLE reconciliation_match (
    match_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenant(tenant_id) ON DELETE CASCADE,
    transaction_id UUID NOT NULL REFERENCES normalized_transaction(transaction_id) ON DELETE CASCADE,
    settlement_id UUID REFERENCES psp_settlement(settlement_id) ON DELETE SET NULL,
    match_level INTEGER NOT NULL, -- 1=strong ID, 2=PSP ref, 3=fuzzy, 4=amount+date
    confidence_score NUMERIC(5, 2) NOT NULL, -- 0-100
    match_method VARCHAR(50) NOT NULL, -- AUTO, MANUAL, RULE
    amount_difference BIGINT, -- cents (transaction amount - settlement amount)
    amount_difference_percent NUMERIC(5, 2),
    matched_by_user_id UUID, -- NULL for auto-matches
    matched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status VARCHAR(50) NOT NULL DEFAULT 'MATCHED', -- MATCHED, PARTIAL_MATCH, PENDING_REVIEW
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, transaction_id, settlement_id)
) PARTITION BY RANGE ((SELECT transaction_date FROM normalized_transaction WHERE transaction_id = reconciliation_match.transaction_id));

-- Indexes for reconciliation_match
CREATE INDEX idx_reconciliation_match_tenant_date 
    ON reconciliation_match (tenant_id, matched_at);
CREATE INDEX idx_reconciliation_match_transaction 
    ON reconciliation_match (transaction_id);
CREATE INDEX idx_reconciliation_match_settlement 
    ON reconciliation_match (settlement_id);
CREATE INDEX idx_reconciliation_match_status 
    ON reconciliation_match (tenant_id, status, matched_at);

-- ============================================================================
-- RECONCILIATION EXCEPTIONS
-- ============================================================================

CREATE TABLE reconciliation_exception (
    exception_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenant(tenant_id) ON DELETE CASCADE,
    transaction_id UUID REFERENCES normalized_transaction(transaction_id) ON DELETE CASCADE,
    settlement_id UUID REFERENCES psp_settlement(settlement_id) ON DELETE CASCADE,
    exception_type VARCHAR(50) NOT NULL, -- UNMATCHED, PARTIAL_MATCH, AMOUNT_MISMATCH, DUPLICATE
    exception_reason TEXT,
    amount_value BIGINT, -- cents
    amount_currency VARCHAR(3),
    priority VARCHAR(10) NOT NULL DEFAULT 'P3', -- P1, P2, P3, P4
    status VARCHAR(50) NOT NULL DEFAULT 'OPEN', -- OPEN, UNDER_REVIEW, RESOLVED, EXPECTED
    assigned_to_user_id UUID,
    resolved_by_user_id UUID,
    resolved_at TIMESTAMPTZ,
    resolution_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_reconciliation_exception_tenant_status 
    ON reconciliation_exception (tenant_id, status, created_at);
CREATE INDEX idx_reconciliation_exception_transaction 
    ON reconciliation_exception (transaction_id);
CREATE INDEX idx_reconciliation_exception_priority 
    ON reconciliation_exception (tenant_id, priority, status);

-- ============================================================================
-- MANUAL ADJUSTMENTS
-- ============================================================================

CREATE TABLE manual_adjustment (
    adjustment_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenant(tenant_id) ON DELETE CASCADE,
    exception_id UUID REFERENCES reconciliation_exception(exception_id),
    adjustment_type VARCHAR(50) NOT NULL, -- MANUAL_MATCH, AMOUNT_CORRECTION, VOID
    amount_value BIGINT NOT NULL, -- cents
    amount_currency VARCHAR(3) NOT NULL,
    description TEXT NOT NULL,
    created_by_user_id UUID NOT NULL,
    approved_by_user_id UUID,
    approval_status VARCHAR(50) NOT NULL DEFAULT 'PENDING', -- PENDING, APPROVED, REJECTED
    approval_required BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    approved_at TIMESTAMPTZ,
    metadata JSONB
);

CREATE INDEX idx_manual_adjustment_tenant_status 
    ON manual_adjustment (tenant_id, approval_status, created_at);

-- ============================================================================
-- LEDGER ENTRIES (Double-Entry Accounting)
-- ============================================================================

CREATE TABLE ledger_entry (
    ledger_entry_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenant(tenant_id) ON DELETE CASCADE,
    entity_id UUID NOT NULL REFERENCES entity(entity_id) ON DELETE CASCADE,
    transaction_date DATE NOT NULL,
    account_debit VARCHAR(100) NOT NULL, -- Chart of accounts code
    account_credit VARCHAR(100) NOT NULL,
    amount BIGINT NOT NULL, -- cents
    currency VARCHAR(3) NOT NULL,
    reference_transaction_id UUID REFERENCES normalized_transaction(transaction_id),
    reference_match_id UUID REFERENCES reconciliation_match(match_id),
    reference_adjustment_id UUID REFERENCES manual_adjustment(adjustment_id),
    description TEXT NOT NULL,
    posted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    posted_by_system BOOLEAN NOT NULL DEFAULT true,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (transaction_date);

CREATE INDEX idx_ledger_entry_tenant_date 
    ON ledger_entry (tenant_id, transaction_date);
CREATE INDEX idx_ledger_entry_entity_date 
    ON ledger_entry (entity_id, transaction_date);
CREATE INDEX idx_ledger_entry_accounts 
    ON ledger_entry (account_debit, account_credit, transaction_date);

-- Create partition for current month
CREATE TABLE ledger_entry_2024_01 
    PARTITION OF ledger_entry
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- ============================================================================
-- CHARGEBACKS & DISPUTES
-- ============================================================================

CREATE TABLE chargeback (
    chargeback_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenant(tenant_id) ON DELETE CASCADE,
    transaction_id UUID NOT NULL REFERENCES normalized_transaction(transaction_id) ON DELETE CASCADE,
    psp_chargeback_id VARCHAR(255) NOT NULL,
    chargeback_reason VARCHAR(100),
    chargeback_reason_code VARCHAR(50),
    chargeback_amount BIGINT NOT NULL, -- cents
    chargeback_currency VARCHAR(3) NOT NULL,
    chargeback_date DATE NOT NULL,
    dispute_deadline DATE,
    status VARCHAR(50) NOT NULL DEFAULT 'INITIATED', -- INITIATED, UNDER_REVIEW, ACCEPTED, DISPUTED, WON, LOST, REVERSED
    dispute_evidence JSONB,
    assigned_to_user_id UUID,
    resolved_at TIMESTAMPTZ,
    resolved_by_user_id UUID,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, psp_chargeback_id)
);

CREATE INDEX idx_chargeback_tenant_status 
    ON chargeback (tenant_id, status, chargeback_date);
CREATE INDEX idx_chargeback_transaction 
    ON chargeback (transaction_id);

-- ============================================================================
-- USERS & RBAC
-- ============================================================================

CREATE TABLE "user" (
    user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID REFERENCES tenant(tenant_id) ON DELETE CASCADE, -- NULL for platform admins
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(50) NOT NULL, -- PLATFORM_ADMIN, TENANT_ADMIN, FINANCE_DIRECTOR, FINANCE_MANAGER, RECONCILIATION_ANALYST, AUDITOR
    sso_provider VARCHAR(50), -- AWS_SSO, OKTA, AZURE_AD, OIDC
    sso_external_id VARCHAR(255), -- External SSO user ID
    mfa_enabled BOOLEAN NOT NULL DEFAULT false,
    status VARCHAR(50) NOT NULL DEFAULT 'ACTIVE', -- ACTIVE, INACTIVE, SUSPENDED
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_user_tenant 
    ON "user" (tenant_id, status);
CREATE INDEX idx_user_email 
    ON "user" (email);

-- ============================================================================
-- RECONCILIATION RULES
-- ============================================================================

CREATE TABLE reconciliation_rule (
    rule_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenant(tenant_id) ON DELETE CASCADE,
    rule_name VARCHAR(255) NOT NULL,
    rule_description TEXT,
    rule_type VARCHAR(50) NOT NULL, -- MATCHING, EXCEPTION, ALERT
    conditions JSONB NOT NULL, -- Rule conditions (flexible schema)
    actions JSONB NOT NULL, -- Rule actions (flexible schema)
    priority INTEGER NOT NULL DEFAULT 100, -- Lower = higher priority
    enabled BOOLEAN NOT NULL DEFAULT true,
    created_by_user_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_reconciliation_rule_tenant 
    ON reconciliation_rule (tenant_id, enabled, priority);

-- ============================================================================
-- FX RATES
-- ============================================================================

CREATE TABLE fx_rate (
    fx_rate_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    from_currency VARCHAR(3) NOT NULL,
    to_currency VARCHAR(3) NOT NULL,
    rate_date DATE NOT NULL,
    rate NUMERIC(10, 6) NOT NULL,
    rate_source VARCHAR(50) NOT NULL, -- ECB, OANDA, MANUAL
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(from_currency, to_currency, rate_date)
);

CREATE INDEX idx_fx_rate_date 
    ON fx_rate (rate_date, from_currency, to_currency);

-- ============================================================================
-- AUDIT LOGS (Append-Only, Immutable)
-- ============================================================================

CREATE TABLE audit_log (
    audit_log_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID REFERENCES tenant(tenant_id) ON DELETE SET NULL,
    user_id UUID REFERENCES "user"(user_id) ON DELETE SET NULL,
    action VARCHAR(50) NOT NULL, -- CREATE, UPDATE, DELETE, APPROVE, EXPORT, LOGIN, etc.
    resource_type VARCHAR(50) NOT NULL, -- TRANSACTION, MATCH, ADJUSTMENT, USER, etc.
    resource_id UUID,
    old_value JSONB,
    new_value JSONB,
    ip_address VARCHAR(45), -- IPv4 or IPv6
    user_agent TEXT,
    metadata JSONB,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (timestamp);

CREATE INDEX idx_audit_log_tenant_timestamp 
    ON audit_log (tenant_id, timestamp);
CREATE INDEX idx_audit_log_user_timestamp 
    ON audit_log (user_id, timestamp);
CREATE INDEX idx_audit_log_resource 
    ON audit_log (resource_type, resource_id, timestamp);

-- Create partition for current month
CREATE TABLE audit_log_2024_01 
    PARTITION OF audit_log
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- ============================================================================
-- ROW-LEVEL SECURITY (RLS) POLICIES
-- ============================================================================

ALTER TABLE normalized_transaction ENABLE ROW LEVEL SECURITY;
ALTER TABLE psp_settlement ENABLE ROW LEVEL SECURITY;
ALTER TABLE reconciliation_match ENABLE ROW LEVEL SECURITY;
ALTER TABLE reconciliation_exception ENABLE ROW LEVEL SECURITY;
ALTER TABLE ledger_entry ENABLE ROW LEVEL SECURITY;
ALTER TABLE chargeback ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Users can only access data for their tenant
-- (Platform admins bypass via service role)
CREATE POLICY tenant_isolation_normalized_transaction 
    ON normalized_transaction
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID);

CREATE POLICY tenant_isolation_psp_settlement 
    ON psp_settlement
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID);

CREATE POLICY tenant_isolation_reconciliation_match 
    ON reconciliation_match
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID);

CREATE POLICY tenant_isolation_reconciliation_exception 
    ON reconciliation_exception
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID);

CREATE POLICY tenant_isolation_ledger_entry 
    ON ledger_entry
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID);

CREATE POLICY tenant_isolation_chargeback 
    ON chargeback
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID);

CREATE POLICY tenant_isolation_audit_log 
    ON audit_log
    FOR SELECT
    USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID OR tenant_id IS NULL);

-- ============================================================================
-- FUNCTIONS & TRIGGERS
-- ============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply updated_at triggers
CREATE TRIGGER update_tenant_updated_at BEFORE UPDATE ON tenant
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_brand_updated_at BEFORE UPDATE ON brand
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_entity_updated_at BEFORE UPDATE ON entity
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_psp_connection_updated_at BEFORE UPDATE ON psp_connection
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_normalized_transaction_updated_at BEFORE UPDATE ON normalized_transaction
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_psp_settlement_updated_at BEFORE UPDATE ON psp_settlement
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_reconciliation_match_updated_at BEFORE UPDATE ON reconciliation_match
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_reconciliation_exception_updated_at BEFORE UPDATE ON reconciliation_exception
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_chargeback_updated_at BEFORE UPDATE ON chargeback
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_user_updated_at BEFORE UPDATE ON "user"
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_reconciliation_rule_updated_at BEFORE UPDATE ON reconciliation_rule
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


