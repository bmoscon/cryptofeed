# Cryptofeed Engineering Principles & AI Development Guide

## Active Specifications
- `cryptofeed-proxy-integration`: HTTP and WebSocket proxy support with transparent Pydantic v2 configuration, enabling per-exchange SOCKS4/SOCKS5 and HTTP proxy overrides without code changes
- `proxy-integration-testing`: Comprehensive proxy integration tests for HTTP and WebSocket clients across CCXT and native cryptofeed exchanges

### Proxy Testing Workflow
- Test commands: `pytest tests/unit/test_proxy_mvp.py tests/integration/test_proxy_http.py tests/integration/test_proxy_ws.py`
- CI: `.github/workflows/tests.yml` runs matrix with and without `python-socks`
- Documentation: `docs/proxy/user-guide.md#test-execution`, summary in `docs/proxy/testing.md`

## Core Engineering Principles

### SOLID Principles
- **Single Responsibility**: Each class/module has one reason to change
- **Open/Closed**: Open for extension, closed for modification
- **Liskov Substitution**: Derived classes must be substitutable for base classes
- **Interface Segregation**: Clients shouldn't depend on interfaces they don't use
- **Dependency Inversion**: Depend on abstractions, not concretions

### KISS (Keep It Simple, Stupid)
- Prefer simple solutions over complex ones
- Avoid premature optimization
- Write code that is easy to understand and maintain
- Minimize cognitive load for future developers

### DRY (Don't Repeat Yourself)
- Extract common functionality into reusable components
- Use configuration over duplication
- Share metadata/transport logic across derived feeds
- Avoid duplicated rate limit logic

### YAGNI (You Aren't Gonna Need It)
- Implement only what's needed now
- Defer features until they're actually required
- Keep configuration surface minimal
- Avoid building for hypothetical future requirements

## Development Standards

### NO MOCKS
- Use real implementations with test fixtures
- Prefer integration tests over heavily mocked unit tests
- Test against actual exchange APIs when possible
- Use ccxt sandbox or permissive endpoints for testing

### NO LEGACY
- Remove deprecated code aggressively
- Don't maintain backward compatibility for internal APIs
- Upgrade dependencies regularly
- Clean architecture without legacy workarounds

### NO COMPATIBILITY
- Target latest Python versions
- Use modern language features
- Don't support outdated exchange API versions
- Break APIs when it improves design

### START SMALL
- Begin with MVP implementations
- Support minimal viable feature set first
- Add complexity only when justified
- Iterative development over big bang releases

### CONSISTENT NAMING WITHOUT PREFIXES
- Use clear, descriptive names
- Avoid Hungarian notation or type prefixes
- Consistent verb tenses (get/set, fetch/push)
- Domain-specific terminology over generic names

## Agentic Coding Best Practices

### Research-Plan-Execute Workflow
1. **Research Phase**: Read relevant files, understand context
2. **Planning Phase**: Outline solution architecture
3. **Execution Phase**: Implement with continuous verification
4. **Validation Phase**: Test and verify implementation

### Test-Driven Development (TDD)
- Write tests first based on expected behavior
- Run tests to confirm they fail
- Implement minimal code to pass tests
- Refactor without changing test behavior
- Never modify tests to fit implementation

### Context Engineering
- Maintain project context in CLAUDE.md
- Use specific, actionable instructions
- Provide file paths and screenshots for UI work
- Reference existing patterns and conventions
- Clear context between major tasks

### Iterative Development
- Make small, verifiable changes
- Commit frequently with descriptive messages
- Use subagents for complex verification tasks
- Review code changes continuously
- Maintain clean git history

## Context Engineering Principles

### Information Architecture
- **Prioritize by Relevance**: Most important information first
- **Logical Categorization**: Group related context together
- **Progressive Detail**: Start essential, add layers gradually
- **Clear Relationships**: Show dependencies and connections

### Dynamic Context Systems
- **Runtime Context**: Generate context on-demand for tasks
- **State Management**: Track conversation and project state
- **Memory Integration**: Combine short-term and long-term knowledge
- **Tool Integration**: Provide relevant tool and API context

### Context Optimization
- **Precision Over Volume**: Quality information over quantity
- **Format Consistency**: Structured, scannable information
- **Relevance Filtering**: Include only task-relevant context
- **Context Window Management**: Efficient use of available space

## Cryptofeed-Specific Guidelines

### Exchange Integration
- Use ccxt for standardized exchange APIs
- Follow existing emitter/queue patterns
- Implement proper rate limiting and backoff
- Handle regional restrictions with proxy support

### Data Normalization
- Convert timestamps to consistent float seconds
- Use Decimal for price/quantity precision
- Preserve sequence numbers for gap detection
- Normalize symbols via ccxt helpers

### Error Handling
- Surface HTTP errors with actionable messages
- Provide fallback modes (REST-only, alternative endpoints)
- Log warnings for experimental features
- Implement graceful degradation

### Configuration
- Use YAML configuration files
- Support environment variable interpolation
- Provide clear examples and documentation
- Allow per-deployment customization

### Architecture Patterns
```
CcxtGenericFeed
 ├─ CcxtMetadataCache   → ccxt.exchange.load_markets()
 ├─ CcxtRestTransport   → ccxt.async_support.exchange.fetch_*()
 └─ CcxtWsTransport     → ccxt.pro.exchange.watch_*()
      ↳ CcxtEmitter     → existing BackendQueue/Metrics
```

## Testing Strategy

### Unit Testing
- Mock ccxt transports for isolated testing
- Test symbol normalization and data transformation
- Verify queue integration and error handling
- Assert configuration parsing and validation

### Integration Testing
- Test against live exchange APIs (sandbox when available)
- Verify trade/L2 callback sequences
- Test with actual proxy configurations
- Record sample payloads for regression testing

### Regression Testing
- Maintain docker-compose test harnesses
- Test across ccxt version updates
- Verify backward compatibility of configurations
- Automated testing in CI/CD pipeline

## Common Commands

### Development
```bash
# Run tests
python -m pytest tests/ -v

# Type checking
mypy cryptofeed/

# Linting
ruff check cryptofeed/
ruff format cryptofeed/

# Install development dependencies
pip install -e ".[dev]"
```

### Exchange Testing
```bash
# Test specific exchange integration
python -m pytest tests/integration/test_backpack.py -v

# Run with live data (requires credentials)
BACKPACK_API_KEY=xxx python examples/backpack_live.py
```

### Documentation
```bash
# Build docs
cd docs && make html

# Serve docs locally
cd docs/_build/html && python -m http.server 8000
```

## AI Development Workflow

### Task Initialization
1. Read this CLAUDE.md file for context
2. Examine relevant specification files in `docs/specs/`
3. Review existing implementation patterns
4. Plan approach using established principles

### Implementation Process
1. Write tests first (TDD approach)
2. Implement minimal viable solution
3. Iterate with continuous testing
4. Refactor for clarity and maintainability
5. Document configuration and usage

### Quality Assurance
1. Run full test suite
2. Check type annotations
3. Verify code formatting
4. Test with real exchange data
5. Update documentation as needed

### Code Review Checklist
- [ ] Follows SOLID principles
- [ ] Implements TDD approach
- [ ] No mocks in production code
- [ ] Consistent naming conventions
- [ ] Proper error handling
- [ ] Type annotations present
- [ ] Tests cover edge cases
- [ ] Documentation updated
- [ ] No legacy compatibility code
- [ ] Configuration examples provided

## Project Structure

```
cryptofeed/
├── adapters/           # ccxt integration adapters
├── exchanges/          # exchange-specific implementations
├── defines.py          # constants and enums
├── types.py           # type definitions
└── utils.py           # utility functions

docs/
├── specs/             # detailed specifications
├── examples/          # usage examples
└── api/              # API documentation

tests/
├── unit/             # isolated unit tests
├── integration/      # live exchange tests
└── fixtures/         # test data and mocks
```

## Performance Considerations

### Memory Management
- Use slots for data classes
- Implement proper cleanup in transports
- Monitor memory usage in long-running feeds
- Use generators for large data streams

### Network Optimization
- Implement connection pooling
- Use persistent WebSocket connections
- Batch REST API requests when possible
- Implement proper rate limiting

### Data Processing
- Use Decimal for financial calculations
- Minimize data copying in hot paths
- Implement efficient order book management
- Cache metadata to reduce API calls

---

*This document serves as the primary context for AI-assisted development in the Cryptofeed project. Update regularly as patterns and practices evolve.*
