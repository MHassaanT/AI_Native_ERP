"""Unit tests ensuring all models adhere to Multi-Tenancy invariants."""

from erp.db.models import (
    BOM,
    Account,
    AgentAuditLog,
    Base,
    CostCenter,
    Customer,
    Employee,
    ExpenseClaim,
    FiscalPeriod,
    GeneralLedgerEntry,
    GoodsReceiptNote,
    Item,
    MaintenanceTicket,
    PurchaseOrder,
    SalesOrder,
    SalesQuotation,
    SemanticDocumentEmbedding,
    ShiftSchedule,
    StockLedgerEntry,
    StockLevel,
    Supplier,
    SupplierInvoice,
    TransactionalOutbox,
    Warehouse,
    WorkOrder,
    Workstation,
)


def test_all_models_have_tenant_id():
    """Validates that every single operational and ledger table enforces multi-tenancy."""
    tables = Base.metadata.tables

    # Child item tables that belong to parent documents may inherit tenant isolation through parent FK
    # but all top-level operational and ledger tables must have tenant_id column
    required_tenant_models = [
        GeneralLedgerEntry,
        Account,
        CostCenter,
        FiscalPeriod,
        TransactionalOutbox,
        AgentAuditLog,
        SemanticDocumentEmbedding,
        Item,
        Warehouse,
        StockLedgerEntry,
        StockLevel,
        Supplier,
        PurchaseOrder,
        GoodsReceiptNote,
        SupplierInvoice,
        Workstation,
        BOM,
        WorkOrder,
        MaintenanceTicket,
        Customer,
        SalesQuotation,
        SalesOrder,
        Employee,
        ShiftSchedule,
        ExpenseClaim,
    ]

    for model in required_tenant_models:
        table_name = model.__tablename__
        assert table_name in tables, f"Table {table_name} not registered in Base metadata"
        columns = tables[table_name].columns
        assert "tenant_id" in columns, (
            f"CRITICAL: Model {model.__name__} (table '{table_name}') is missing 'tenant_id' column required for multi-tenancy"
        )
