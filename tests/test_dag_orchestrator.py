"""Unit Tests for Hierarchical DAG Task Orchestrator."""

import uuid

import pytest

from erp.orchestration.dag import TaskDAG
from erp.orchestration.orchestrator import chief_orchestrator


class TestDAGOrchestrator:
    """Tests Directed Acyclic Graph builder and execution engine."""

    def test_dag_creation_and_topological_readiness(self):
        dag = TaskDAG(dag_id="test_dag_01")
        t1 = dag.add_node(name="Task 1", agent_id="REVENUE")
        t2 = dag.add_node(name="Task 2", agent_id="SUPPLY_CHAIN", dependencies=[t1.task_id])
        t3 = dag.add_node(name="Task 3", agent_id="PRODUCTION", dependencies=[t1.task_id])
        t4 = dag.add_node(name="Task 4", agent_id="REVENUE", dependencies=[t2.task_id, t3.task_id])

        # Initially, only t1 is ready
        ready = dag.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].task_id == t1.task_id

        # Mark t1 completed -> t2 and t3 should become ready
        dag.mark_completed(t1.task_id, {"status": "parsed"})
        ready_2 = dag.get_ready_tasks()
        assert len(ready_2) == 2
        ready_ids = {t.task_id for t in ready_2}
        assert t2.task_id in ready_ids
        assert t3.task_id in ready_ids

        # Mark t2 completed -> t4 is still not ready because t3 is pending
        dag.mark_completed(t2.task_id, {"cost": 150})
        ready_3 = dag.get_ready_tasks()
        assert len(ready_3) == 0

        # Mark t3 completed -> t4 becomes ready
        dag.mark_completed(t3.task_id, {"makespan": 4.5})
        ready_4 = dag.get_ready_tasks()
        assert len(ready_4) == 1
        assert ready_4[0].task_id == t4.task_id

        # Mark t4 completed -> DAG is finished
        dag.mark_completed(t4.task_id, {"quote_id": "Q-100"})
        assert dag.is_finished() is True

    def test_cycle_detection_raises_error(self):
        dag = TaskDAG(dag_id="cycle_dag")
        t1 = dag.add_node(name="Task A", agent_id="REVENUE")
        t2 = dag.add_node(name="Task B", agent_id="SUPPLY_CHAIN", dependencies=[t1.task_id])

        # Attempt to add cyclic dependency: Task A depends on Task B
        with pytest.raises(ValueError, match="Cycle detected"):
            # Manually inject cycle to test validator
            t1.dependencies.add(t2.task_id)
            dag.validate()

    def test_build_rfq_workflow_dag(self):
        tenant_id = uuid.uuid4()
        dag = chief_orchestrator.build_rfq_workflow_dag(
            tenant_id=tenant_id,
            rfq_payload={"sku": "FG-ENCLOSURE-IP67", "quantity": 500},
        )
        assert len(dag.nodes) == 4
        ready = dag.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].agent_id == "REVENUE"
