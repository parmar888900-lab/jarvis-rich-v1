"""Tests for the persistent production operation model."""

from backend.models.production_operation import (
    ProductionOperationRecord,
    ProductionOperationStatus,
)


def main():
    table = ProductionOperationRecord.__table__

    assert (
        table.name
        == "production_operations"
    )

    expected_columns = {
        "id",
        "idempotency_key",
        "operation_type",
        "resource_id",
        "status",
        "result",
        "error",
        "created_at",
        "started_at",
        "completed_at",
    }

    assert set(
        table.columns.keys()
    ) == expected_columns

    assert (
        table.c.idempotency_key.nullable
        is False
    )

    assert (
        table.c.operation_type.nullable
        is False
    )

    assert (
        table.c.resource_id.nullable
        is False
    )

    assert (
        table.c.status.nullable
        is False
    )

    constraints = list(
        table.constraints
    )

    unique_constraints = [
        constraint
        for constraint in constraints
        if (
            constraint.__class__.__name__
            == "UniqueConstraint"
        )
    ]

    assert len(unique_constraints) == 1

    unique_columns = {
        column.name
        for column
        in unique_constraints[0].columns
    }

    assert unique_columns == {
        "idempotency_key"
    }

    assert (
        ProductionOperationStatus.PENDING.value
        == "pending"
    )
    assert (
        ProductionOperationStatus.IN_PROGRESS.value
        == "in_progress"
    )
    assert (
        ProductionOperationStatus.COMPLETED.value
        == "completed"
    )
    assert (
        ProductionOperationStatus.FAILED.value
        == "failed"
    )

    print("=" * 70)
    print(
        "PRODUCTION OPERATION "
        "MODEL TEST"
    )
    print()

    print(
        "PASS: production operation "
        "schema is correct."
    )
    print(
        "PASS: idempotency key "
        "is uniquely constrained."
    )
    print(
        "PASS: required operation "
        "fields are non-nullable."
    )
    print(
        "PASS: operation lifecycle "
        "states are defined."
    )

    print()
    print("=" * 70)
    print(
        "ALL PRODUCTION OPERATION "
        "MODEL TESTS PASSED"
    )


if __name__ == "__main__":
    main()
