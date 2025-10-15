# Test Suite Guide

This directory contains comprehensive test suites for the Procrastinate task queue system.

## Test Files

### 1. `test_durability.py` - Durability Tests
Tests the reliability and persistence of the task queue system:

- **TestTaskDurability**: Task persistence, worker restarts, retry behavior, idempotency
- **TestQueueDurability**: Queue ordering (FIFO), queueing locks, multiple queue independence
- **TestJobRecovery**: Job retry mechanisms, exponential backoff timing
- **TestDataConsistency**: Transaction rollback, concurrency safety, state immutability
- **TestJobPriority**: Priority-based execution, scheduled tasks
- **TestWorkerResilience**: Worker fault tolerance, task timeout protection

**Key Features Tested:**
- Tasks persist across worker restarts
- Failed tasks retry correctly with exponential backoff
- Successful tasks execute exactly once (idempotency)
- Concurrent tasks don't interfere with each other
- Queueing locks prevent duplicate jobs
- Data consistency under failures

### 2. `test_throughput.py` - Performance & Throughput Tests
Tests the performance characteristics and scalability:

- **TestBasicThroughput**: Single task execution time, sequential throughput, deferral rate
- **TestConcurrentThroughput**: Concurrent processing, parallel deferral performance
- **TestBatchProcessing**: Small and large batch throughput
- **TestLoadPerformance**: Sustained load, burst load, mixed priority loads
- **TestTaskExecutionLatency**: Latency distribution, queue wait times
- **TestWorkerEfficiency**: Worker utilization, idle overhead
- **TestScalability**: Throughput scaling, memory efficiency
- **TestPerformanceRegression**: Baseline metrics, consistency checks

**Key Metrics Measured:**
- Tasks processed per second
- Task deferral rate
- Queue wait time and latency
- Worker efficiency and utilization
- Performance consistency across runs
- Memory efficiency

### 3. `test_exponential_backoff.py` - Unit Tests
Unit tests for the exponential backoff retry strategy:
- Exponential delay calculation
- Max attempts enforcement
- Max delay capping
- Exception filtering

### 4. `test_integration.py` - Integration Tests
Integration tests for task execution with real components:
- Task retry behavior with mocked APIs
- Timeout protection
- Exception handling
- Idempotency verification

## Running the Tests

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Run All Tests
```bash
pytest tests/ -v
```

### Run Specific Test Files

**Durability Tests:**
```bash
pytest tests/test_durability.py -v
```

**Throughput Tests:**
```bash
pytest tests/test_throughput.py -v -s
```
Note: Use `-s` to see performance metrics printed to console

**Unit Tests:**
```bash
pytest tests/test_exponential_backoff.py -v
```

**Integration Tests:**
```bash
pytest tests/test_integration.py -v
```

### Run Specific Test Classes
```bash
pytest tests/test_durability.py::TestTaskDurability -v
pytest tests/test_throughput.py::TestBasicThroughput -v
```

### Run Specific Test Methods
```bash
pytest tests/test_durability.py::TestTaskDurability::test_task_persists_in_queue -v
pytest tests/test_throughput.py::TestBasicThroughput::test_sequential_task_throughput -v -s
```

### Run with Coverage
```bash
pytest tests/ --cov=app --cov-report=html
```

### Run Tests in Parallel
```bash
pytest tests/ -n auto
```
(Requires `pytest-xdist`)

## Test Fixtures

### Available Fixtures (from `conftest.py`)

1. **`event_loop`** (session scope)
   - Provides async event loop for the test session

2. **`mock_settings`**
   - Mock settings object for isolated testing

3. **`in_memory_connector`**
   - In-memory Procrastinate connector (no database required)
   - Automatically resets after each test

4. **`in_memory_app`**
   - Complete Procrastinate app with in-memory connector
   - Perfect for fast unit tests without database

5. **`performance_threshold`**
   - Performance threshold values for throughput tests

## Test Patterns

### Using In-Memory Connector
```python
@pytest.mark.asyncio
async def test_example(in_memory_app):
    # Defer a task
    await my_task.defer_async(param="value")
    
    # Check queued jobs
    jobs = in_memory_app.connector.jobs
    assert len(jobs) == 1
    
    # Run worker
    await in_memory_app.run_worker_async(wait=False)
    
    # Verify execution
    assert jobs[0].status == 'succeeded'
```

### Measuring Performance
```python
@pytest.mark.asyncio
async def test_throughput(in_memory_app):
    import time
    
    # Defer tasks
    start = time.perf_counter()
    for i in range(100):
        await task.defer_async(value=i)
    elapsed = time.perf_counter() - start
    
    # Calculate metrics
    throughput = 100 / elapsed
    print(f"Throughput: {throughput:.2f} tasks/second")
```

### Testing Failures
```python
@pytest.mark.asyncio
async def test_retry(in_memory_app):
    @in_memory_app.task(
        queue="test",
        retry=ExponentialBackoffStrategy(max_attempts=3, base_delay=1.0)
    )
    async def failing_task():
        raise TaskError("Simulated failure")
    
    await failing_task.defer_async()
    
    with pytest.raises(TaskError):
        await in_memory_app.run_worker_async(wait=False)
```

## Performance Benchmarks

### Expected Performance (In-Memory Connector)
Based on the test suite, you should expect:

- **Deferral Rate**: > 50-200 tasks/second
- **Processing Rate**: > 10-50 tasks/second
- **Single Task Latency**: < 100ms
- **Batch Processing**: Scales linearly up to hundreds of tasks
- **Queue Wait Time**: Minimal (< 100ms) under normal load

Note: These are benchmarks for in-memory testing. Real database performance will vary.

## Continuous Integration

### GitHub Actions Example
```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pytest tests/ -v --cov=app
```

## Troubleshooting

### Tests Running Slowly
- Make sure you're using in-memory connector for unit tests
- Use `pytest-xdist` for parallel execution
- Check for unnecessary `await asyncio.sleep()` calls

### Async Test Warnings
- Ensure `pytest-asyncio` is installed
- Use `@pytest.mark.asyncio` decorator on async tests
- Check `event_loop` fixture scope

### Import Errors
- Ensure all dependencies are installed: `pip install -r requirements.txt`
- Check that `PYTHONPATH` includes project root
- Verify virtual environment is activated

## Best Practices

1. **Isolate Tests**: Use in-memory connector for unit tests
2. **Measure Performance**: Use `-s` flag to see performance metrics
3. **Test Edge Cases**: Include timeout, failure, and concurrent scenarios
4. **Document Thresholds**: Update performance thresholds as system evolves
5. **Run Regularly**: Include in CI/CD pipeline

## Adding New Tests

When adding new tests:

1. Choose appropriate test file based on test type
2. Use existing fixtures from `conftest.py`
3. Follow naming conventions: `test_<feature>_<scenario>`
4. Add docstrings explaining what's being tested
5. Include performance assertions where relevant
6. Clean up resources (use fixtures for automatic cleanup)

## References

- [Procrastinate Documentation](https://procrastinate.readthedocs.io/)
- [Procrastinate Testing Guide](https://procrastinate.readthedocs.io/en/stable/howto/production/testing.html)
- [pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
