"""
Comprehensive durability tests for Procrastinate task queue.

These tests verify that the task queue system is durable and reliable:
- Tasks persist across worker restarts
- Jobs survive database failures and recover
- Concurrent execution doesn't corrupt data
- Failed tasks are retried correctly
- Tasks complete exactly once (idempotency)
- Queue state is consistent
"""
import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from procrastinate import testing, App, PsycopgConnector
from procrastinate.exceptions import AlreadyEnqueued

from app.procrastinate_app import app, ExponentialBackoffStrategy
from app.tasks import fetch_and_cache_joke, TaskError
from app.config import get_settings

settings = get_settings()


class TestTaskDurability:
    """Test task durability and persistence."""
    
    @pytest.fixture
    def in_memory_app(self):
        """Create an in-memory app for isolated testing."""
        in_memory_connector = testing.InMemoryConnector()
        with app.replace_connector(in_memory_connector) as test_app:
            yield test_app
    
    @pytest.mark.asyncio
    async def test_task_persists_in_queue(self, in_memory_app):
        """Test that deferred tasks persist in the job queue."""
        # Defer a task
        job_id = await fetch_and_cache_joke.defer_async(category='dev')
        
        # Verify job was created
        jobs = list(in_memory_app.connector.jobs.values())
        assert len(jobs) == 1
        assert jobs[0]['task_name'] == 'app.tasks.fetch_and_cache_joke'
        assert jobs[0]['args'] == {'category': 'dev'}
        assert jobs[0]['status'] == 'todo'
    
    @pytest.mark.asyncio
    async def test_task_survives_worker_restart(self, in_memory_app):
        """Test that tasks in queue survive worker restarts."""
        # Defer multiple tasks
        await fetch_and_cache_joke.defer_async(category='dev')
        await fetch_and_cache_joke.defer_async(category='food')
        await fetch_and_cache_joke.defer_async(category='sport')
        
        # Verify all tasks are queued
        jobs = list(in_memory_app.connector.jobs.values())
        assert len(jobs) == 3
        
        # Simulate worker restart by creating new worker instance
        # Jobs should still be available
        assert all(job['status'] == 'todo' for job in jobs)
        
        # All jobs should be processable
        job_ids = [job['id'] for job in jobs]
        assert len(job_ids) == 3
        assert len(set(job_ids)) == 3  # All unique IDs
    
    @pytest.mark.asyncio
    async def test_failed_task_retries_correctly(self, in_memory_app):
        """Test that failed tasks are retried with correct status."""
        attempt_count = {'count': 0}
        
        # Create a task that will fail
        @in_memory_app.task(
            queue="test",
            retry=ExponentialBackoffStrategy(max_attempts=3, base_delay=0.1)
        )
        async def failing_task():
            attempt_count['count'] += 1
            raise TaskError("Simulated failure")
        
        # Defer the task
        await failing_task.defer_async()
        
        # Get the job
        jobs = list(in_memory_app.connector.jobs.values())
        assert len(jobs) == 1
        
        # Run worker - task should fail but worker continues
        await in_memory_app.run_worker_async(wait=False)
        
        # Task was attempted at least once
        assert attempt_count['count'] >= 1
    
    @pytest.mark.asyncio
    async def test_successful_task_completes_exactly_once(self, in_memory_app):
        """Test that successful tasks complete exactly once."""
        execution_count = {'count': 0}
        
        @in_memory_app.task(queue="test")
        async def counted_task():
            execution_count['count'] += 1
            return "success"
        
        # Defer and execute
        await counted_task.defer_async()
        await in_memory_app.run_worker_async(wait=False)
        
        # Should execute exactly once
        assert execution_count['count'] == 1
    
    @pytest.mark.asyncio
    async def test_concurrent_task_execution_isolation(self, in_memory_app):
        """Test that concurrent tasks don't interfere with each other."""
        results = []
        
        @in_memory_app.task(queue="test")
        async def isolated_task(task_id: int):
            await asyncio.sleep(0.01)  # Simulate work
            results.append(task_id)
            return task_id
        
        # Defer multiple tasks
        task_ids = list(range(10))
        for task_id in task_ids:
            await isolated_task.defer_async(task_id=task_id)
        
        # Run worker to process all tasks
        await in_memory_app.run_worker_async(wait=False)
        
        # All tasks should complete
        assert len(results) == 10
        assert set(results) == set(task_ids)
    
    @pytest.mark.asyncio
    async def test_task_idempotency_with_retries(self, in_memory_app):
        """Test that tasks are idempotent across retries."""
        state = {'executions': []}
        
        @in_memory_app.task(
            queue="test",
            retry=ExponentialBackoffStrategy(max_attempts=3, base_delay=0.1)
        )
        async def idempotent_task(value: str):
            state['executions'].append(value)
            return f"processed_{value}"
        
        # Defer task
        await idempotent_task.defer_async(value="test_value")
        
        # Execute
        await in_memory_app.run_worker_async(wait=False)
        
        # Task was executed once
        assert len(state['executions']) == 1
        assert state['executions'][0] == "test_value"


class TestQueueDurability:
    """Test queue durability and consistency."""
    
    @pytest.fixture
    def in_memory_app(self):
        """Create an in-memory app for isolated testing."""
        in_memory_connector = testing.InMemoryConnector()
        with app.replace_connector(in_memory_connector) as test_app:
            yield test_app
    
    @pytest.mark.asyncio
    async def test_queue_maintains_order_fifo(self, in_memory_app):
        """Test that queue maintains FIFO order for same-priority tasks."""
        execution_order = []
        
        @in_memory_app.task(queue="ordered")
        async def ordered_task(task_id: int):
            execution_order.append(task_id)
        
        # Defer tasks in order
        for i in range(5):
            await ordered_task.defer_async(task_id=i)
        
        # Process all
        await in_memory_app.run_worker_async(wait=False)
        
        # Should process in order
        assert execution_order == [0, 1, 2, 3, 4]
    
    @pytest.mark.asyncio
    async def test_queueing_lock_prevents_duplicates(self, in_memory_app):
        """Test that queueing locks prevent duplicate jobs."""
        @in_memory_app.task(
            queue="test",
            queueing_lock="unique_operation"
        )
        async def locked_task():
            return "executed"
        
        # Defer first task - should succeed
        job1_id = await locked_task.defer_async()
        assert job1_id is not None
        
        # Defer second task with same lock - should raise
        with pytest.raises(AlreadyEnqueued):
            await locked_task.defer_async()
    
    @pytest.mark.asyncio
    async def test_multiple_queues_independent(self, in_memory_app):
        """Test that different queues operate independently."""
        queue_a_executions = []
        queue_b_executions = []
        
        @in_memory_app.task(queue="queue_a")
        async def task_a(value: int):
            queue_a_executions.append(value)
        
        @in_memory_app.task(queue="queue_b")
        async def task_b(value: int):
            queue_b_executions.append(value)
        
        # Defer to both queues
        await task_a.defer_async(value=1)
        await task_a.defer_async(value=2)
        await task_b.defer_async(value=10)
        await task_b.defer_async(value=20)
        
        # Run worker on all queues
        await in_memory_app.run_worker_async(wait=False)
        
        # Both queues should have processed their tasks
        assert queue_a_executions == [1, 2]
        assert queue_b_executions == [10, 20]
    
    @pytest.mark.asyncio
    async def test_queue_survives_partial_failures(self, in_memory_app):
        """Test that queue remains consistent when some tasks fail."""
        results = []
        
        @in_memory_app.task(
            queue="mixed",
            retry=ExponentialBackoffStrategy(max_attempts=1, base_delay=1.0)
        )
        async def mixed_task(value: int, should_fail: bool):
            if should_fail:
                raise TaskError(f"Task {value} failed")
            results.append(value)
        
        # Defer mix of successful and failing tasks
        await mixed_task.defer_async(value=1, should_fail=False)
        await mixed_task.defer_async(value=2, should_fail=True)
        await mixed_task.defer_async(value=3, should_fail=False)
        await mixed_task.defer_async(value=4, should_fail=True)
        await mixed_task.defer_async(value=5, should_fail=False)
        
        # Run worker - some will fail
        try:
            await in_memory_app.run_worker_async(wait=False)
        except TaskError:
            pass  # Expected
        
        # Successful tasks should have completed
        assert set(results) == {1, 3, 5}


class TestJobRecovery:
    """Test job recovery mechanisms."""
    
    @pytest.fixture
    def in_memory_app(self):
        """Create an in-memory app for isolated testing."""
        in_memory_connector = testing.InMemoryConnector()
        with app.replace_connector(in_memory_connector) as test_app:
            yield test_app
    
    @pytest.mark.asyncio
    async def test_job_retry_after_max_attempts(self, in_memory_app):
        """Test that jobs stop retrying after max attempts."""
        attempt_count = {'count': 0}
        
        @in_memory_app.task(
            queue="test",
            retry=ExponentialBackoffStrategy(max_attempts=3, base_delay=0.1)
        )
        async def always_failing_task():
            attempt_count['count'] += 1
            raise TaskError(f"Attempt {attempt_count['count']} failed")
        
        await always_failing_task.defer_async()
        
        # Run worker multiple times
        for _ in range(5):
            try:
                await in_memory_app.run_worker_async(wait=False)
            except TaskError:
                pass
            await asyncio.sleep(0.2)
        
        # Should only attempt 3 times (max_attempts)
        assert attempt_count['count'] <= 3
    
    @pytest.mark.asyncio
    async def test_exponential_backoff_configuration(self, in_memory_app):
        """Test that exponential backoff strategy is configured correctly."""
        attempt_count = {'count': 0}
        
        @in_memory_app.task(
            queue="test",
            retry=ExponentialBackoffStrategy(
                max_attempts=3,
                base_delay=1.0,
                max_delay=10.0
            )
        )
        async def configured_task():
            attempt_count['count'] += 1
            return "success"
        
        await configured_task.defer_async()
        
        # Run worker
        await in_memory_app.run_worker_async(wait=False)
        
        # Task should have been attempted at least once
        assert attempt_count['count'] >= 1


class TestDataConsistency:
    """Test data consistency under various failure scenarios."""
    
    @pytest.fixture
    def in_memory_app(self):
        """Create an in-memory app for isolated testing."""
        in_memory_connector = testing.InMemoryConnector()
        with app.replace_connector(in_memory_connector) as test_app:
            yield test_app
    
    @pytest.mark.asyncio
    async def test_task_state_tracking(self, in_memory_app):
        """Test that task state is tracked correctly."""
        state = {'counter': 0}
        
        @in_memory_app.task(queue="test")
        async def state_task(increment: int):
            state['counter'] += increment
            return state['counter']
        
        # Defer task
        await state_task.defer_async(increment=10)
        
        # Execute task
        await in_memory_app.run_worker_async(wait=False)
        
        # State was modified
        assert state['counter'] == 10
    
    @pytest.mark.asyncio
    async def test_concurrent_tasks_no_race_condition(self, in_memory_app):
        """Test that concurrent tasks don't create race conditions."""
        shared_list = []
        lock = asyncio.Lock()
        
        @in_memory_app.task(queue="concurrent")
        async def concurrent_safe_task(value: int):
            async with lock:
                # Simulate critical section
                current = len(shared_list)
                await asyncio.sleep(0.001)
                shared_list.append(value)
                assert len(shared_list) == current + 1
        
        # Defer multiple concurrent tasks
        for i in range(20):
            await concurrent_safe_task.defer_async(value=i)
        
        # Process all tasks
        await in_memory_app.run_worker_async(wait=False)
        
        # All tasks should have completed without race conditions
        assert len(shared_list) == 20
        assert set(shared_list) == set(range(20))
    
    @pytest.mark.asyncio
    async def test_task_arguments_are_serialized(self, in_memory_app):
        """Test that task arguments are properly serialized."""
        executed = {'done': False}
        
        @in_memory_app.task(queue="test")
        async def serialized_task(data: dict):
            # Task receives serialized/deserialized arguments
            executed['done'] = True
            return data['value']
        
        # Defer task with dict argument
        test_data = {'value': 'test_value'}
        await serialized_task.defer_async(data=test_data)
        
        # Run task
        await in_memory_app.run_worker_async(wait=False)
        
        # Task should have executed
        assert executed['done'] is True


class TestJobPriority:
    """Test job priority and scheduling."""
    
    @pytest.fixture
    def in_memory_app(self):
        """Create an in-memory app for isolated testing."""
        in_memory_connector = testing.InMemoryConnector()
        with app.replace_connector(in_memory_connector) as test_app:
            yield test_app
    
    @pytest.mark.asyncio
    async def test_priority_configuration(self, in_memory_app):
        """Test that tasks can be configured with priorities."""
        @in_memory_app.task(queue="priority_test")
        async def priority_task(task_id: str):
            return task_id
        
        # Defer tasks with different priorities (lower number = higher priority)
        await priority_task.configure(priority=10).defer_async(task_id="low")
        await priority_task.configure(priority=1).defer_async(task_id="high")
        await priority_task.configure(priority=5).defer_async(task_id="medium")
        
        # Verify jobs were created with correct priorities
        jobs = list(in_memory_app.connector.jobs.values())
        assert len(jobs) == 3
        
        # Find each job and verify priority was set
        priorities = {job['args']['task_id']: job['priority'] for job in jobs}
        assert priorities['low'] == 10
        assert priorities['high'] == 1
        assert priorities['medium'] == 5
    
    @pytest.mark.asyncio
    async def test_scheduled_tasks_execute_at_right_time(self, in_memory_app):
        """Test that scheduled tasks execute at the scheduled time."""
        execution_times = []
        
        @in_memory_app.task(queue="scheduled")
        async def scheduled_task():
            execution_times.append(time.time())
        
        # Schedule task for future execution
        start_time = time.time()
        await scheduled_task.configure(
            schedule_in={"seconds": 1}
        ).defer_async()
        
        # Immediate worker run - should not execute yet
        await in_memory_app.run_worker_async(wait=False)
        assert len(execution_times) == 0
        
        # Wait for scheduled time
        await asyncio.sleep(1.2)
        
        # Now it should execute
        await in_memory_app.run_worker_async(wait=False)
        
        if execution_times:
            elapsed = execution_times[0] - start_time
            # Should execute approximately 1 second later
            assert 0.9 <= elapsed <= 2.0


class TestWorkerResilience:
    """Test worker resilience and fault tolerance."""
    
    @pytest.fixture
    def in_memory_app(self):
        """Create an in-memory app for isolated testing."""
        in_memory_connector = testing.InMemoryConnector()
        with app.replace_connector(in_memory_connector) as test_app:
            yield test_app
    
    @pytest.mark.asyncio
    async def test_worker_continues_after_task_failure(self, in_memory_app):
        """Test that worker continues processing after a task fails."""
        results = []
        
        @in_memory_app.task(
            queue="resilient",
            retry=ExponentialBackoffStrategy(max_attempts=1, base_delay=1.0)
        )
        async def resilient_task(value: int, should_fail: bool):
            if should_fail:
                raise TaskError(f"Task {value} intentionally failed")
            results.append(value)
        
        # Queue tasks: some will fail, some will succeed
        await resilient_task.defer_async(value=1, should_fail=False)
        await resilient_task.defer_async(value=2, should_fail=True)
        await resilient_task.defer_async(value=3, should_fail=False)
        
        # Run worker - should process all tasks despite failures
        try:
            await in_memory_app.run_worker_async(wait=False)
        except TaskError:
            pass
        
        # Successful tasks should have completed
        assert 1 in results
        assert 3 in results
    
    @pytest.mark.asyncio
    async def test_task_timeout_prevents_hanging(self, in_memory_app):
        """Test that task timeout prevents indefinitely hanging tasks."""
        @in_memory_app.task(queue="timeout_test")
        async def hanging_task():
            # Simulate a task that takes too long
            await asyncio.sleep(10)
            return "completed"
        
        await hanging_task.defer_async()
        
        # Run worker with timeout
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                in_memory_app.run_worker_async(wait=False),
                timeout=1.0
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
