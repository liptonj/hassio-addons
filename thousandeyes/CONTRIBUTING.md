# Contributing to ThousandEyes Enterprise Agent Add-on

Thank you for your interest in contributing! This document provides guidelines for contributing to this Home Assistant add-on.

## Code of Conduct

Please be respectful and constructive in all interactions. We're all here to make this add-on better.

## How to Contribute

### Reporting Issues

When reporting issues, please include:
- Home Assistant version
- Add-on version
- Relevant log output (from the add-on Log tab)
- Steps to reproduce the issue
- Expected vs actual behavior

### Suggesting Features

Feature requests are welcome! Please:
- Check if the feature is already requested
- Describe the use case clearly
- Explain why it would be useful to others
- Consider if it should be an add-on feature or a ThousandEyes portal configuration

### Code Contributions

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/your-feature-name`
3. **Make your changes**
4. **Test thoroughly** (see Testing section below)
5. **Follow coding standards** (see below)
6. **Submit a pull request**

## Development Setup

### Prerequisites

- Home Assistant installation (Supervisor required for add-ons)
- SSH or Samba access to Home Assistant
- Text editor or IDE
- Git

### Local Development

1. Clone the repository to your `/addons` directory
2. Make changes to the files
3. Reload the add-on store in Home Assistant
4. Install/update your local version
5. Test your changes

### Testing Locations

- **Basic Startup**: Check logs for successful startup
- **Configuration**: Test various configuration combinations
- **Proxy**: Test with and without proxy settings
- **DNS**: Test custom DNS configuration
- **ThousandEyes Portal**: Verify agent appears and tests run
- **Resource Limits**: Verify memory and CPU limits work
- **Logs**: Verify logging levels work correctly

## Coding Standards

### Python (if adding Python scripts)

- Follow PEP 8 style guidelines
- Use type hints where applicable
- Include docstrings for functions
- Add unit tests for new functionality

### Bash Scripts

- Use shellcheck for linting
- Add comments for complex logic
- Handle errors gracefully
- Use bashio functions for Home Assistant integration
- Follow the existing logging patterns

### YAML Files

- Use 2-space indentation
- Follow Home Assistant add-on schema
- Validate YAML syntax before committing
- Keep comments clear and helpful

### Documentation

- Update README.md for user-facing changes
- Update DOCS.md for detailed documentation
- Add entries to CHANGELOG.md
- Include examples for new features

## Pull Request Process

1. **Update documentation** for any changed functionality
2. **Add CHANGELOG entry** under "Unreleased" section
3. **Test your changes** on a real Home Assistant installation
4. **Describe your changes** clearly in the PR description
5. **Reference related issues** using #issue-number
6. **Be responsive** to review feedback

### PR Description Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Configuration change
- [ ] Other (describe)

## Testing
Describe how you tested these changes

## Checklist
- [ ] Tested on Home Assistant
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] No linting errors
- [ ] Follows coding standards
```

## Architecture Guidelines

### File Structure

- `config.yaml` - Add-on configuration and schema
- `Dockerfile` - Container build instructions
- `run.sh` - Startup script (bash)
- `README.md` - User documentation
- `DOCS.md` - Detailed documentation
- `CHANGELOG.md` - Version history
- `build.yaml` - Build configuration

### Adding Configuration Options

When adding new configuration options:

1. **Add to config.yaml**:
   - Add to `options` section with sensible default
   - Add to `schema` section with correct type
   - Use `?` suffix for optional fields

2. **Update run.sh**:
   - Read the option using bashio
   - Validate if necessary
   - Set appropriate environment variable
   - Add logging

3. **Document in README.md**:
   - Add to appropriate section
   - Include description, default, and example
   - Explain when to use it

4. **Document in DOCS.md**:
   - Add detailed explanation
   - Include troubleshooting if relevant

### Logging Standards

Use appropriate bashio log levels:
- `bashio::log.debug` - Detailed debugging info
- `bashio::log.info` - Normal operation info
- `bashio::log.warning` - Important notices
- `bashio::log.error` - Errors that need attention
- `bashio::log.fatal` - Critical errors before exit

### Error Handling

- Validate required configuration early
- Provide clear error messages
- Use `bashio::exit.nok` for fatal errors
- Log errors before exiting
- Handle missing optional configuration gracefully

## Security Considerations

- Never log sensitive data (tokens, passwords)
- Use `password` type in schema for sensitive fields
- Document security implications of new features
- Follow principle of least privilege
- Keep dependencies updated

## Version Management

We follow [Semantic Versioning](https://semver.org/):
- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes

## Getting Help

- Check existing issues and PRs
- Read the documentation thoroughly
- Test locally before asking
- Provide context when asking questions

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.

## Recognition

Contributors will be recognized in:
- GitHub contributors list
- CHANGELOG.md for significant contributions
- README.md credits section (for major features)

Thank you for contributing! 🎉

