#!/usr/bin/env python3
"""Validate migration fixes."""
import re

def test_migration_022():
    """Test migration 022 version column widening."""
    # Read migration file as text
    with open("alembic/versions/022_add_employee_attendance_token.py") as f:
        content = f.read()
    
    # Extract revision ID
    revision_match = re.search(r'revision: str = "([^"]+)"', content)
    assert revision_match, "Could not find revision ID"
    revision = revision_match.group(1)
    
    print(f"Migration 022 revision: {revision}")
    print(f"Revision length: {len(revision)}")
    assert len(revision) == 33, f"Expected 33 chars, got {len(revision)}"
    
    # Check that upgrade contains VARCHAR(255) widening
    assert "VARCHAR(255)" in content, "upgrade() should widen to VARCHAR(255)"
    assert "alembic_version" in content, "upgrade() should reference alembic_version"
    
    print("✓ Migration 022 validation passed")

def test_migration_023():
    """Test migration 023 designation column drop."""
    with open("alembic/versions/023_drop_old_designation_column.py") as f:
        content = f.read()
    
    # Extract revision ID
    revision_match = re.search(r'revision: str = "([^"]+)"', content)
    assert revision_match, "Could not find revision ID"
    revision = revision_match.group(1)
    
    down_revision_match = re.search(r'down_revision: str = "([^"]+)"', content)
    assert down_revision_match, "Could not find down_revision"
    down_revision = down_revision_match.group(1)
    
    print(f"Migration 023 revision: {revision}")
    assert revision == "023_drop_old_designation_column"
    assert down_revision == "022_add_employee_attendance_token"
    
    # Check that upgrade drops the designation column
    assert "drop_column" in content, "upgrade() should drop designation column"
    assert "designation" in content, "upgrade() should reference designation"
    
    print("✓ Migration 023 validation passed")

def test_employee_model():
    """Test that Employee model no longer has old designation column."""
    with open("src/erp/db/models/hr.py") as f:
        content = f.read()
    
    # The model should have designation_id
    assert "designation_id" in content, "Model should have designation_id"
    
    # Ensure no standalone 'designation' mapped_column exists
    lines = content.split('\n')
    has_old_designation = any(
        'designation:' in l and 'designation_id' not in l and 'mapped_column' in l
        for l in lines
    )
    assert not has_old_designation, "Model should not have old designation field"
    
    print("✓ Employee model validation passed")

def test_department_service():
    """Test that create_department has idempotency check."""
    with open("src/erp/workflows/hr/employee_service.py") as f:
        content = f.read()
    
    # Find the create_department function
    import re
    create_dept_match = re.search(
        r'async def create_department\(.*?\n(?:.*?\n)*?return dept',
        content,
        re.DOTALL
    )
    assert create_dept_match, "Could not find create_department function"
    func_content = create_dept_match.group(0)
    
    assert "select" in func_content.lower(), "create_department should have a select query"
    assert "existing" in func_content.lower(), "create_department should check for existing department"
    
    print("✓ Department service validation passed")

if __name__ == "__main__":
    try:
        test_migration_022()
        test_migration_023()
        test_employee_model()
        test_department_service()
        print("\n✅ All validation tests passed")
    except Exception as e:
        print(f"\n❌ Validation failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
