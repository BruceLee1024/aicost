CREATE TABLE IF NOT EXISTS projects (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    region VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS boq_items (
    id SERIAL PRIMARY KEY,
    project_id INT NOT NULL REFERENCES projects(id),
    code VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    unit VARCHAR(50) NOT NULL,
    quantity DOUBLE PRECISION NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS quota_items (
    id SERIAL PRIMARY KEY,
    quota_code VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    unit VARCHAR(50) NOT NULL,
    labor_qty DOUBLE PRECISION NOT NULL DEFAULT 0,
    material_qty DOUBLE PRECISION NOT NULL DEFAULT 0,
    machine_qty DOUBLE PRECISION NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS line_item_quota_bindings (
    id SERIAL PRIMARY KEY,
    boq_item_id INT NOT NULL REFERENCES boq_items(id),
    quota_item_id INT NOT NULL REFERENCES quota_items(id),
    coefficient DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    CONSTRAINT uq_boq_quota_binding UNIQUE (boq_item_id, quota_item_id)
);

CREATE TABLE IF NOT EXISTS calc_results (
    id SERIAL PRIMARY KEY,
    boq_item_id INT NOT NULL REFERENCES boq_items(id),
    total_cost DOUBLE PRECISION NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS material_prices (
    id SERIAL PRIMARY KEY,
    code VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    spec VARCHAR(255) DEFAULT '',
    unit VARCHAR(50) NOT NULL,
    unit_price DOUBLE PRECISION NOT NULL DEFAULT 0,
    source VARCHAR(100) NOT NULL DEFAULT 'manual',
    region VARCHAR(100) NOT NULL DEFAULT '',
    effective_date VARCHAR(20) NOT NULL DEFAULT '1970-01-01'
);

CREATE TABLE IF NOT EXISTS project_valuation_configs (
    id SERIAL PRIMARY KEY,
    project_id INT NOT NULL UNIQUE REFERENCES projects(id),
    standard_code VARCHAR(100) NOT NULL DEFAULT 'GB/T50500-2024',
    standard_name VARCHAR(255) NOT NULL DEFAULT '建设工程工程量清单计价标准',
    effective_date VARCHAR(20) NOT NULL DEFAULT '2025-09-01',
    locked_at VARCHAR(50) DEFAULT NULL,
    updated_at VARCHAR(50) NOT NULL
);

CREATE TABLE IF NOT EXISTS contract_measurements (
    id SERIAL PRIMARY KEY,
    project_id INT NOT NULL REFERENCES projects(id),
    boq_item_id INT NOT NULL REFERENCES boq_items(id),
    period_label VARCHAR(100) NOT NULL DEFAULT '',
    measured_qty DOUBLE PRECISION NOT NULL DEFAULT 0,
    cumulative_qty DOUBLE PRECISION NOT NULL DEFAULT 0,
    status VARCHAR(50) NOT NULL DEFAULT 'draft',
    approved_by VARCHAR(100) NOT NULL DEFAULT '',
    approved_at VARCHAR(50) NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    created_at VARCHAR(50) NOT NULL
);

CREATE TABLE IF NOT EXISTS price_adjustments (
    id SERIAL PRIMARY KEY,
    project_id INT NOT NULL REFERENCES projects(id),
    boq_item_id INT DEFAULT NULL,
    adjustment_type VARCHAR(100) NOT NULL DEFAULT 'change_order',
    amount DOUBLE PRECISION NOT NULL DEFAULT 0,
    status VARCHAR(50) NOT NULL DEFAULT 'draft',
    reason TEXT NOT NULL DEFAULT '',
    created_at VARCHAR(50) NOT NULL
);

CREATE TABLE IF NOT EXISTS payment_certificates (
    id SERIAL PRIMARY KEY,
    project_id INT NOT NULL REFERENCES projects(id),
    period_label VARCHAR(100) NOT NULL DEFAULT '',
    gross_amount DOUBLE PRECISION NOT NULL DEFAULT 0,
    prepayment_deduction DOUBLE PRECISION NOT NULL DEFAULT 0,
    retention DOUBLE PRECISION NOT NULL DEFAULT 0,
    net_payable DOUBLE PRECISION NOT NULL DEFAULT 0,
    paid_amount DOUBLE PRECISION NOT NULL DEFAULT 0,
    status VARCHAR(50) NOT NULL DEFAULT 'issued',
    issued_at VARCHAR(50) NOT NULL
);
