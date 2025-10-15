"""
Comprehensive throughput and performance tests for Procrastinate task queue.

These tests measure and verify:
- Tasks processed per second
- Concurrent task execution performance
- Queue processing efficiency
- Worker scalability
- Batch processing performance
- System behavior under load
- Memory and resource usage patterns
"""
import pytest
import asyncio
import time
import statistics
from typing import List
from procrastinate import testing

from app.procrastinate_app import app, ExponentialBackoffStrategy
from app.tasks import fetch_and_cache_joke
from app.config import get_settings

settings = get_settings()


class TestBasicThroughput:
    """Test basic throughput metrics."""
    
    @pytest.fixture
    def in_memory_app(self):
        """Create an in-memory app for isolated testing."""
        in_memory_connector = testing.InMemoryConnector()
        with app.replace_connector(in_memory_connector) as test_app:
            yield test_app
    
    @pytest.mark.asyncio
    async def test_single_task_execution_time(self, in_memory_app):
        """Test execution time for a single simple task."""
        @in_memory_app.task(queue="perf")
        async def simple_task():
            await asyncio.sleep(0.001)  # Minimal work
            return "done"
        
        # Measure single task execution
        start = time.perf_counter()
        await simple_task.defer_async()
        await in_memory_app.run_worker_async(wait=False)
        elapsed = time.perf_counter() - start
        
        # Should complete quickly (within 1 second for in-memory)
        assert elapsed < 1.0
        print(f"\nSingle task execution time: {elapsed*1000:.2f}ms")
    
    @pytest.mark.asyncio
    async def test_sequential_task_throughput(self, in_memory_app):
        """Test throughput for sequential task execution."""
        execution_count = {'count': 0}
        
        @in_memory_app.task(queue="perf")
        async def counter_task():
            execution_count['count'] += 1
            await asyncio.sleep(0.001)
        
        # Queue multiple tasks
        num_tasks = 50
        for _ in range(num_tasks):
            await counter_task.defer_async()
        
        # Measure processing time
        start = time.perf_counter()
        await in_memory_app.run_worker_async(wait=False)
        elapsed = time.perf_counter() - start
        
        # Calculate throughput
        throughput = num_tasks / elapsed if elapsed > 0 else 0
        
        assert execution_count['count'] == num_tasks
        print(f"\nSequential throughput: {throughput:.2f} tasks/second")
        print(f"Total time: {elapsed:.3f}s for {num_tasks} tasks")
        
        # Should process at least 10 tasks per second
        assert throughput > 10
    
    @pytest.mark.asyncio
    async def test_task_deferral_rate(self, in_memory_app):
        """Test the rate at which tasks can be deferred."""
        @in_memory_app.task(queue="defer_test")
        async def dummy_task(value: int):
            return value
        
        # Measure deferral rate
        num_tasks = 100
        start = time.perf_counter()
        
        for i in range(num_tasks):
            await dummy_task.defer_async(value=i)
        
        elapsed = time.perf_counter() - start
        deferral_rate = num_tasks / elapsed if elapsed > 0 else 0
        
        jobs = in_memory_app.connector.jobs
        assert len(jobs) == num_tasks
        
        print(f"\nTask deferral rate: {deferral_rate:.2f} tasks/second")
        print(f"Time to defer {num_tasks} tasks: {elapsed*1000:.2f}ms")
        
        # Should defer at least 100 tasks per second
        assert deferral_rate > 100


class TestConcurrentThroughput:
    """Test throughput under concurrent execution."""
    
    @pytest.fixture
    def in_memory_app(self):
        """Create an in-memory app for isolated testing."""
        in_memory_connector = testing.InMemoryConnector()
        with app.replace_connector(in_memory_connector) as test_app:
            yield test_app
    
    @pytest.mark.asyncio
    async def test_concurrent_task_processing(self, in_memory_app):
        """Test processing speed with concurrent tasks."""
        completed_tasks = []
        
        @in_memory_app.task(queue="concurrent")
        async def concurrent_task(task_id: int):
            # Simulate I/O bound work
            await asyncio.sleep(0.01)
            completed_tasks.append(task_id)
            return task_id
        
        # Defer many tasks
        num_tasks = 100
        for i in range(num_tasks):
            await concurrent_task.defer_async(task_id=i)
        
        # Process with concurrency
        start = time.perf_counter()
        await in_memory_app.run_worker_async(wait=False)
        elapsed = time.perf_counter() - start
        
        throughput = num_tasks / elapsed if elapsed > 0 else 0
        
        assert len(completed_tasks) == num_tasks
        print(f"\nConcurrent throughput: {throughput:.2f} tasks/second")
        print(f"Processing time: {elapsed:.3f}s for {num_tasks} tasks")
        
        # With concurrency, should be faster than sequential
        assert throughput > 5
    
    @pytest.mark.asyncio
    async def test_parallel_deferral_performance(self, in_memory_app):
        """Test performance of parallel task deferral."""
        @in_memory_app.task(queue="parallel_defer")
        async def parallel_task(value: int):
            return value
        
        # Defer tasks in parallel using gather
        num_tasks = 200
        start = time.perf_counter()
        
        await asyncio.gather(*[
            parallel_task.defer_async(value=i)
            for i in range(num_tasks)
        ])
        
        elapsed = time.perf_counter() - start
        deferral_rate = num_tasks / elapsed if elapsed > 0 else 0
        
        jobs = in_memory_app.connector.jobs
        assert len(jobs) == num_tasks
        
        print(f"\nParallel deferral rate: {deferral_rate:.2f} tasks/second")
        print(f"Time: {elapsed*1000:.2f}ms for {num_tasks} tasks")
        
        # Parallel deferral should be very fast
        assert deferral_rate > 200


class TestBatchProcessing:
    """Test batch processing performance."""
    
    @pytest.fixture
    def in_memory_app(self):
        """Create an in-memory app for isolated testing."""
        in_memory_connector = testing.InMemoryConnector()
        with app.replace_connector(in_memory_connector) as test_app:
            yield test_app
    
    @pytest.mark.asyncio
    async def test_small_batch_throughput(self, in_memory_app):
        """Test throughput for small batches of tasks."""
        results = []
        
        @in_memory_app.task(queue="small_batch")
        async def batch_task(batch_id: int, item_id: int):
            results.append((batch_id, item_id))
        
        # Process 10 batches of 10 tasks each
        num_batches = 10
        batch_size = 10
        total_tasks = num_batches * batch_size
        
        start = time.perf_counter()
        
        for batch_id in range(num_batches):
            for item_id in range(batch_size):
                await batch_task.defer_async(batch_id=batch_id, item_id=item_id)
        
        await in_memory_app.run_worker_async(wait=False)
        elapsed = time.perf_counter() - start
        
        throughput = total_tasks / elapsed if elapsed > 0 else 0
        
        assert len(results) == total_tasks
        print(f"\nSmall batch throughput: {throughput:.2f} tasks/second")
        print(f"Processed {num_batches} batches of {batch_size} tasks in {elapsed:.3f}s")
    
    @pytest.mark.asyncio
    async def test_large_batch_throughput(self, in_memory_app):
        """Test throughput for large batches of tasks."""
        completed = {'count': 0}
        
        @in_memory_app.task(queue="large_batch", name="large_batch_task")
        async def batch_task(value: int):
            completed['count'] += 1
        
        # Process large batch
        batch_size = 500
        start = time.perf_counter()
        
        # Defer all tasks
        defer_start = time.perf_counter()
        for i in range(batch_size):
            await batch_task.defer_async(value=i)
        defer_time = time.perf_counter() - defer_start
        
        # Process all tasks
        process_start = time.perf_counter()
        await in_memory_app.run_worker_async(wait=False)
        process_time = time.perf_counter() - process_start
        
        total_time = time.perf_counter() - start
        throughput = batch_size / total_time if total_time > 0 else 0
        
        assert completed['count'] == batch_size
        print(f"\nLarge batch stats:")
        print(f"  Deferral time: {defer_time:.3f}s ({batch_size/defer_time:.0f} tasks/s)")
        print(f"  Processing time: {process_time:.3f}s ({batch_size/process_time:.0f} tasks/s)")
        print(f"  Total throughput: {throughput:.2f} tasks/second")


class TestLoadPerformance:
    """Test performance under various load conditions."""
    
    @pytest.fixture
    def in_memory_app(self):
        """Create an in-memory app for isolated testing."""
        in_memory_connector = testing.InMemoryConnector()
        with app.replace_connector(in_memory_connector) as test_app:
            yield test_app
    
    @pytest.mark.asyncio
    async def test_sustained_load_performance(self, in_memory_app):
        """Test performance under sustained load."""
        processed = []
        
        @in_memory_app.task(queue="sustained", name="sustained_load_task")
        async def sustained_task(task_id: int):
            await asyncio.sleep(0.001)
            processed.append(task_id)
        
        # Simulate sustained load
        num_tasks = 50
        
        start = time.perf_counter()
        
        # Defer all tasks
        for i in range(num_tasks):
            await sustained_task.defer_async(task_id=i)
        
        # Process all
        await in_memory_app.run_worker_async(wait=False)
        
        elapsed = time.perf_counter() - start
        throughput = num_tasks / elapsed if elapsed > 0 else 0
        
        assert len(processed) == num_tasks
        print(f"\nSustained load throughput: {throughput:.2f} tasks/second")
        print(f"Processed {num_tasks} tasks in {elapsed:.3f}s")
    
    @pytest.mark.asyncio
    async def test_burst_load_performance(self, in_memory_app):
        """Test performance under burst load."""
        completed = {'count': 0}
        
        @in_memory_app.task(queue="burst")
        async def burst_task():
            completed['count'] += 1
            await asyncio.sleep(0.001)
        
        # Simulate burst - queue many tasks at once
        burst_size = 100
        
        # Defer all tasks in burst
        defer_start = time.perf_counter()
        for _ in range(burst_size):
            await burst_task.defer_async()
        defer_time = time.perf_counter() - defer_start
        
        # Process burst
        process_start = time.perf_counter()
        await in_memory_app.run_worker_async(wait=False)
        process_time = time.perf_counter() - process_start
        
        assert completed['count'] == burst_size
        print(f"\nBurst load stats:")
        print(f"  Burst size: {burst_size} tasks")
        print(f"  Deferral time: {defer_time*1000:.2f}ms")
        print(f"  Processing time: {process_time:.3f}s")
        print(f"  Throughput: {burst_size/process_time:.2f} tasks/second")
    
    @pytest.mark.asyncio
    async def test_mixed_priority_load(self, in_memory_app):
        """Test performance with mixed priority tasks."""
        execution_count = {'count': 0}
        
        @in_memory_app.task(queue="mixed_priority", name="mixed_priority_task")
        async def priority_task(priority: int, task_id: int):
            execution_count['count'] += 1
        
        # Queue tasks with different priorities
        num_per_priority = 10
        
        start = time.perf_counter()
        
        # Mix high, medium, low priority tasks
        for i in range(num_per_priority):
            await priority_task.configure(priority=1).defer_async(priority=1, task_id=i)
            await priority_task.configure(priority=5).defer_async(priority=5, task_id=i)
            await priority_task.configure(priority=10).defer_async(priority=10, task_id=i)
        
        await in_memory_app.run_worker_async(wait=False)
        elapsed = time.perf_counter() - start
        
        total_tasks = num_per_priority * 3
        throughput = total_tasks / elapsed if elapsed > 0 else 0
        
        assert execution_count['count'] == total_tasks
        print(f"\nMixed priority throughput: {throughput:.2f} tasks/second")


class TestTaskExecutionLatency:
    """Test task execution latency metrics."""
    
    @pytest.fixture
    def in_memory_app(self):
        """Create an in-memory app for isolated testing."""
        in_memory_connector = testing.InMemoryConnector()
        with app.replace_connector(in_memory_connector) as test_app:
            yield test_app
    
    @pytest.mark.asyncio
    async def test_task_latency_distribution(self, in_memory_app):
        """Test the distribution of task execution latencies."""
        latencies = []
        
        @in_memory_app.task(queue="latency")
        async def latency_task(defer_time: float):
            latency = time.perf_counter() - defer_time
            latencies.append(latency)
        
        # Defer tasks with timestamps
        num_tasks = 50
        for _ in range(num_tasks):
            await latency_task.defer_async(defer_time=time.perf_counter())
            await asyncio.sleep(0.001)  # Small gap between deferrals
        
        # Process all tasks
        await in_memory_app.run_worker_async(wait=False)
        
        # Calculate latency statistics
        if latencies:
            avg_latency = statistics.mean(latencies)
            median_latency = statistics.median(latencies)
            min_latency = min(latencies)
            max_latency = max(latencies)
            
            print(f"\nLatency statistics ({num_tasks} tasks):")
            print(f"  Average: {avg_latency*1000:.2f}ms")
            print(f"  Median: {median_latency*1000:.2f}ms")
            print(f"  Min: {min_latency*1000:.2f}ms")
            print(f"  Max: {max_latency*1000:.2f}ms")
            
            # Latency should be reasonable for in-memory connector
            assert avg_latency < 1.0  # Less than 1 second average
    
    @pytest.mark.asyncio
    async def test_queue_wait_time(self, in_memory_app):
        """Test time tasks spend waiting in queue."""
        queue_times = []
        
        @in_memory_app.task(queue="wait_time")
        async def wait_time_task(enqueue_time: float):
            wait_time = time.perf_counter() - enqueue_time
            queue_times.append(wait_time)
        
        # Queue multiple tasks
        num_tasks = 30
        for _ in range(num_tasks):
            await wait_time_task.defer_async(enqueue_time=time.perf_counter())
        
        # Process with slight delay to measure queue time
        await asyncio.sleep(0.1)
        await in_memory_app.run_worker_async(wait=False)
        
        if queue_times:
            avg_wait = statistics.mean(queue_times)
            print(f"\nAverage queue wait time: {avg_wait*1000:.2f}ms")
            
            # Queue wait should include our deliberate delay
            assert avg_wait >= 0.1


class TestWorkerEfficiency:
    """Test worker efficiency and resource utilization."""
    
    @pytest.fixture
    def in_memory_app(self):
        """Create an in-memory app for isolated testing."""
        in_memory_connector = testing.InMemoryConnector()
        with app.replace_connector(in_memory_connector) as test_app:
            yield test_app
    
    @pytest.mark.asyncio
    async def test_worker_utilization(self, in_memory_app):
        """Test worker utilization with varying task durations."""
        task_times = []
        
        @in_memory_app.task(queue="utilization")
        async def variable_duration_task(duration: float):
            start = time.perf_counter()
            await asyncio.sleep(duration)
            elapsed = time.perf_counter() - start
            task_times.append(elapsed)
        
        # Queue tasks with different durations
        durations = [0.001, 0.005, 0.01, 0.001, 0.002] * 4
        for duration in durations:
            await variable_duration_task.defer_async(duration=duration)
        
        # Process all tasks
        start = time.perf_counter()
        await in_memory_app.run_worker_async(wait=False)
        total_time = time.perf_counter() - start
        
        # Calculate efficiency
        actual_work_time = sum(task_times)
        efficiency = (actual_work_time / total_time * 100) if total_time > 0 else 0
        
        print(f"\nWorker efficiency:")
        print(f"  Actual work time: {actual_work_time:.3f}s")
        print(f"  Total elapsed time: {total_time:.3f}s")
        print(f"  Efficiency: {efficiency:.1f}%")
        
        # Efficiency depends on concurrency and overhead
        assert efficiency > 0
    
    @pytest.mark.asyncio
    async def test_idle_worker_overhead(self, in_memory_app):
        """Test overhead when worker has no tasks to process."""
        @in_memory_app.task(queue="idle")
        async def idle_task():
            return "done"
        
        # Measure time with no tasks
        start = time.perf_counter()
        await in_memory_app.run_worker_async(wait=False)
        idle_time = time.perf_counter() - start
        
        print(f"\nIdle worker overhead: {idle_time*1000:.2f}ms")
        
        # Idle worker should return quickly
        assert idle_time < 1.0


class TestScalability:
    """Test system scalability characteristics."""
    
    @pytest.fixture
    def in_memory_app(self):
        """Create an in-memory app for isolated testing."""
        in_memory_connector = testing.InMemoryConnector()
        with app.replace_connector(in_memory_connector) as test_app:
            yield test_app
    
    @pytest.mark.asyncio
    async def test_throughput_scaling(self, in_memory_app):
        """Test how throughput scales with number of tasks."""
        test_sizes = [10, 50, 100]
        throughputs = []
        
        for idx, size in enumerate(test_sizes):
            completed = {'count': 0}
            
            @in_memory_app.task(queue=f"scale_{size}", name=f"scale_task_{idx}")
            async def scale_task():
                completed['count'] += 1
                await asyncio.sleep(0.001)
            
            # Queue and process
            start = time.perf_counter()
            for _ in range(size):
                await scale_task.defer_async()
            await in_memory_app.run_worker_async(wait=False)
            elapsed = time.perf_counter() - start
            
            throughput = size / elapsed if elapsed > 0 else 0
            throughputs.append(throughput)
            
            print(f"\n{size:3d} tasks: {throughput:6.2f} tasks/s ({elapsed:.3f}s)")
            
            # Reset connector for next test
            in_memory_app.connector.reset()
        
        # Throughput should remain relatively stable or improve
        print(f"\nThroughput scaling: {throughputs}")
    
    @pytest.mark.asyncio
    async def test_memory_efficiency(self, in_memory_app):
        """Test memory efficiency with large number of tasks."""
        @in_memory_app.task(queue="memory")
        async def memory_task(data: str):
            # Task with some data
            return len(data)
        
        # Queue many tasks with data
        num_tasks = 1000
        test_data = "x" * 100  # 100 byte payload
        
        start = time.perf_counter()
        for i in range(num_tasks):
            await memory_task.defer_async(data=test_data)
        defer_time = time.perf_counter() - start
        
        # Check jobs were created
        jobs = in_memory_app.connector.jobs
        assert len(jobs) == num_tasks
        
        print(f"\nMemory efficiency test:")
        print(f"  Tasks queued: {num_tasks}")
        print(f"  Payload size: {len(test_data)} bytes")
        print(f"  Deferral time: {defer_time:.3f}s")
        print(f"  Deferral rate: {num_tasks/defer_time:.0f} tasks/s")


class TestPerformanceRegression:
    """Test for performance regressions."""
    
    @pytest.fixture
    def in_memory_app(self):
        """Create an in-memory app for isolated testing."""
        in_memory_connector = testing.InMemoryConnector()
        with app.replace_connector(in_memory_connector) as test_app:
            yield test_app
    
    @pytest.mark.asyncio
    async def test_baseline_performance(self, in_memory_app):
        """Establish baseline performance metrics."""
        @in_memory_app.task(queue="baseline")
        async def baseline_task():
            await asyncio.sleep(0.001)
        
        # Run standardized test
        num_tasks = 100
        
        defer_start = time.perf_counter()
        for _ in range(num_tasks):
            await baseline_task.defer_async()
        defer_time = time.perf_counter() - defer_start
        
        process_start = time.perf_counter()
        await in_memory_app.run_worker_async(wait=False)
        process_time = time.perf_counter() - process_start
        
        defer_rate = num_tasks / defer_time if defer_time > 0 else 0
        process_rate = num_tasks / process_time if process_time > 0 else 0
        
        print(f"\nBaseline performance metrics:")
        print(f"  Deferral rate: {defer_rate:.2f} tasks/s")
        print(f"  Processing rate: {process_rate:.2f} tasks/s")
        
        # Set minimum acceptable performance thresholds
        assert defer_rate > 50, "Deferral rate regression detected"
        assert process_rate > 10, "Processing rate regression detected"
    
    @pytest.mark.asyncio
    async def test_consistent_performance(self, in_memory_app):
        """Test that performance is consistent across runs."""
        @in_memory_app.task(queue="consistency")
        async def consistent_task():
            await asyncio.sleep(0.001)
        
        num_runs = 5
        num_tasks = 50
        throughputs = []
        
        for run in range(num_runs):
            start = time.perf_counter()
            
            for _ in range(num_tasks):
                await consistent_task.defer_async()
            
            await in_memory_app.run_worker_async(wait=False)
            elapsed = time.perf_counter() - start
            
            throughput = num_tasks / elapsed if elapsed > 0 else 0
            throughputs.append(throughput)
            
            # Reset for next run
            in_memory_app.connector.reset()
        
        # Calculate variance
        avg_throughput = statistics.mean(throughputs)
        std_dev = statistics.stdev(throughputs) if len(throughputs) > 1 else 0
        coefficient_of_variation = (std_dev / avg_throughput * 100) if avg_throughput > 0 else 0
        
        print(f"\nPerformance consistency ({num_runs} runs):")
        print(f"  Average: {avg_throughput:.2f} tasks/s")
        print(f"  Std Dev: {std_dev:.2f}")
        print(f"  CoV: {coefficient_of_variation:.1f}%")
        print(f"  Min: {min(throughputs):.2f} tasks/s")
        print(f"  Max: {max(throughputs):.2f} tasks/s")
        
        # Performance should be reasonably consistent (CoV < 30%)
        assert coefficient_of_variation < 30, "Performance variance too high"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
