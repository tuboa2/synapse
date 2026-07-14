# Contributing to Synapse

First off, thank you for considering contributing to Synapse! It's people like you that make Synapse such a great tool.

## Code of Conduct

By participating in this project, you are expected to respect and collaborate with others in a positive and professional manner.

## How Can I Contribute?

### Reporting Bugs

- Ensure the bug was not already reported by searching on GitHub under Issues.
- If you're unable to find an open issue addressing the problem, open a new one. Be sure to include a title and clear description, as much relevant information as possible, and a code sample or an executable test case demonstrating the expected behavior that is not occurring.

### Suggesting Enhancements

- Open a new issue with a clear title and description.
- Provide a detailed explanation of the proposed enhancement, including how it works and why it would be useful.

### Pull Requests

1. Fork the repo and create your branch from `main`.
2. If you've added code that should be tested, add tests.
3. If you've changed APIs, update the documentation.
4. Ensure the test suite passes.
5. Make sure your code lints (run `uv run ruff check src` and `uv run mypy src`).
6. Issue that pull request!

## Styleguides

### Git Commit Messages

- Use the present tense ("Add feature" not "Added feature")
- Use the imperative mood ("Move cursor to..." not "Moves cursor to...")
- Limit the first line to 72 characters or less
- Reference issues and pull requests liberally after the first line

### Code Style

We use `ruff` for linting and formatting, and `mypy` for static type checking. Please ensure your code adheres to these standards by running:

```bash
uv run ruff check src
uv run ruff format src
uv run mypy src
```
