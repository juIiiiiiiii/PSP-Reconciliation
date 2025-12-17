-- Additional database functions and utilities

-- ============================================================================
-- IDEMPOTENCY CHECK FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION check_idempotency(
    p_tenant_id UUID,
    p_idempotency_key VARCHAR(255)
)
RETURNS BOOLEAN AS $$
DECLARE
    v_exists BOOLEAN;
BEGIN
    SELECT EXISTS(
        SELECT 1 FROM raw_event_metadata
        WHERE tenant_id = p_tenant_id
        AND idempotency_key = p_idempotency_key
    ) INTO v_exists;
    
    RETURN NOT v_exists; -- Returns true if NOT exists (can process)
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- RECONCILIATION STATS FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION get_reconciliation_stats(
    p_tenant_id UUID,
    p_start_date DATE,
    p_end_date DATE
)
RETURNS TABLE (
    total_transactions BIGINT,
    matched_count BIGINT,
    unmatched_count BIGINT,
    partial_match_count BIGINT,
    match_rate NUMERIC,
    total_exception_value BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(*)::BIGINT as total_transactions,
        COUNT(*) FILTER (WHERE reconciliation_status = 'MATCHED')::BIGINT as matched_count,
        COUNT(*) FILTER (WHERE reconciliation_status = 'UNMATCHED')::BIGINT as unmatched_count,
        COUNT(*) FILTER (WHERE reconciliation_status = 'PARTIAL_MATCH')::BIGINT as partial_match_count,
        CASE 
            WHEN COUNT(*) > 0 THEN 
                (COUNT(*) FILTER (WHERE reconciliation_status = 'MATCHED')::NUMERIC / COUNT(*)::NUMERIC * 100)
            ELSE 0
        END as match_rate,
        COALESCE(SUM(amount_value) FILTER (
            WHERE reconciliation_status IN ('UNMATCHED', 'PARTIAL_MATCH')
        ), 0)::BIGINT as total_exception_value
    FROM normalized_transaction
    WHERE tenant_id = p_tenant_id
    AND transaction_date BETWEEN p_start_date AND p_end_date;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- LEDGER BALANCE FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION get_account_balance(
    p_tenant_id UUID,
    p_entity_id UUID,
    p_account_code VARCHAR(100),
    p_currency VARCHAR(3),
    p_as_of_date DATE
)
RETURNS BIGINT AS $$
DECLARE
    v_balance BIGINT;
BEGIN
    SELECT COALESCE(SUM(
        CASE 
            WHEN account_debit = p_account_code THEN amount
            WHEN account_credit = p_account_code THEN -amount
            ELSE 0
        END
    ), 0)::BIGINT
    INTO v_balance
    FROM ledger_entry
    WHERE tenant_id = p_tenant_id
    AND entity_id = p_entity_id
    AND currency = p_currency
    AND transaction_date <= p_as_of_date
    AND (account_debit = p_account_code OR account_credit = p_account_code);
    
    RETURN v_balance;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- PARTITION MANAGEMENT FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION create_monthly_partition(
    p_table_name TEXT,
    p_partition_date DATE
)
RETURNS VOID AS $$
DECLARE
    v_partition_name TEXT;
    v_start_date DATE;
    v_end_date DATE;
BEGIN
    v_start_date := DATE_TRUNC('month', p_partition_date);
    v_end_date := v_start_date + INTERVAL '1 month';
    v_partition_name := p_table_name || '_' || TO_CHAR(v_start_date, 'YYYY_MM');
    
    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I PARTITION OF %I FOR VALUES FROM (%L) TO (%L)',
        v_partition_name,
        p_table_name,
        v_start_date,
        v_end_date
    );
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- AUDIT LOG TRIGGER FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION log_audit_event()
RETURNS TRIGGER AS $$
DECLARE
    v_old_json JSONB;
    v_new_json JSONB;
    v_user_id UUID;
    v_tenant_id UUID;
BEGIN
    -- Get current user and tenant from session
    v_user_id := current_setting('app.current_user_id', true)::UUID;
    v_tenant_id := current_setting('app.current_tenant_id', true)::UUID;
    
    -- Convert old/new records to JSONB
    IF TG_OP = 'DELETE' THEN
        v_old_json := to_jsonb(OLD);
        v_new_json := NULL;
    ELSIF TG_OP = 'UPDATE' THEN
        v_old_json := to_jsonb(OLD);
        v_new_json := to_jsonb(NEW);
    ELSIF TG_OP = 'INSERT' THEN
        v_old_json := NULL;
        v_new_json := to_jsonb(NEW);
    END IF;
    
    -- Insert audit log
    INSERT INTO audit_log (
        tenant_id,
        user_id,
        action,
        resource_type,
        resource_id,
        old_value,
        new_value
    ) VALUES (
        v_tenant_id,
        v_user_id,
        TG_OP,
        TG_TABLE_NAME,
        COALESCE((NEW.id)::UUID, (OLD.id)::UUID),
        v_old_json,
        v_new_json
    );
    
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    ELSE
        RETURN NEW;
    END IF;
END;
$$ LANGUAGE plpgsql;


