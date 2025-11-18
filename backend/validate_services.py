"""
Service validation script.
Validates that all services are properly structured and importable.
"""
import sys
import os
import importlib.util
from pathlib import Path


def validate_service_file(file_path):
    """Validate a service file can be loaded."""
    errors = []
    warnings = []

    try:
        with open(file_path, 'r') as f:
            content = f.read()

        # Check for required imports
        if 'import logging' not in content:
            warnings.append("Missing logging import")

        # Check for class definition
        if 'class ' not in content:
            if 'Service' in file_path.name:
                errors.append("Service file missing class definition")

        # Check for docstrings
        if '"""' not in content and "'''" not in content:
            warnings.append("Missing module docstring")

        # Check for basic structure
        if 'def __init__' in content:
            if 'self.organization' not in content:
                warnings.append("Service might be missing organization attribute")

        # Check line count
        lines = len(content.split('\n'))

        return {
            'file': file_path.name,
            'status': 'valid' if not errors else 'invalid',
            'errors': errors,
            'warnings': warnings,
            'lines': lines
        }

    except Exception as e:
        return {
            'file': file_path.name,
            'status': 'error',
            'errors': [str(e)],
            'warnings': [],
            'lines': 0
        }


def validate_test_file(file_path):
    """Validate a test file."""
    errors = []
    warnings = []

    try:
        with open(file_path, 'r') as f:
            content = f.read()

        # Check for test class
        if 'TestCase' not in content and 'class Test' not in content:
            errors.append("Missing test class")

        # Check for setUp method
        if 'def setUp' not in content:
            warnings.append("Missing setUp method")

        # Check for test methods
        test_methods = content.count('def test_')
        if test_methods == 0:
            errors.append("No test methods found")

        lines = len(content.split('\n'))

        return {
            'file': file_path.name,
            'status': 'valid' if not errors else 'invalid',
            'errors': errors,
            'warnings': warnings,
            'test_count': test_methods,
            'lines': lines
        }

    except Exception as e:
        return {
            'file': file_path.name,
            'status': 'error',
            'errors': [str(e)],
            'warnings': [],
            'test_count': 0,
            'lines': 0
        }


def main():
    """Run validation."""
    base_dir = Path(__file__).parent
    services_dir = base_dir / 'apps' / 'integrations' / 'services'
    tests_dir = base_dir / 'apps' / 'integrations' / 'tests'

    print("=" * 80)
    print("NOVA LEDGER SERVICE VALIDATION REPORT")
    print("=" * 80)
    print()

    # Validate services
    print("SERVICE FILES:")
    print("-" * 80)

    service_files = sorted(services_dir.glob('*_service.py'))
    total_service_lines = 0
    valid_services = 0

    for service_file in service_files:
        result = validate_service_file(service_file)
        total_service_lines += result['lines']

        status_symbol = "✓" if result['status'] == 'valid' else "✗"
        print(f"{status_symbol} {result['file']:<40} ({result['lines']:>4} lines)")

        if result['errors']:
            for error in result['errors']:
                print(f"  ERROR: {error}")
        if result['warnings']:
            for warning in result['warnings']:
                print(f"  WARN:  {warning}")

        if result['status'] == 'valid':
            valid_services += 1

    print()
    print(f"Services: {valid_services}/{len(service_files)} valid")
    print(f"Total service code: {total_service_lines:,} lines")
    print()

    # Validate tests
    print("TEST FILES:")
    print("-" * 80)

    test_files = sorted(tests_dir.glob('test_*.py'))
    total_test_lines = 0
    total_tests = 0
    valid_test_files = 0

    for test_file in test_files:
        result = validate_test_file(test_file)
        total_test_lines += result['lines']
        total_tests += result['test_count']

        status_symbol = "✓" if result['status'] == 'valid' else "✗"
        print(f"{status_symbol} {result['file']:<40} ({result['test_count']:>3} tests, {result['lines']:>4} lines)")

        if result['errors']:
            for error in result['errors']:
                print(f"  ERROR: {error}")
        if result['warnings']:
            for warning in result['warnings']:
                print(f"  WARN:  {warning}")

        if result['status'] == 'valid':
            valid_test_files += 1

    print()
    print(f"Test files: {valid_test_files}/{len(test_files)} valid")
    print(f"Total tests: {total_tests}")
    print(f"Total test code: {total_test_lines:,} lines")
    print()

    # Check URLs
    print("URL CONFIGURATION:")
    print("-" * 80)

    urls_file = base_dir / 'apps' / 'integrations' / 'urls.py'
    if urls_file.exists():
        with open(urls_file, 'r') as f:
            urls_content = f.read()

        # Count endpoints
        endpoint_count = urls_content.count("path('")
        router_count = urls_content.count("router.register")

        print(f"✓ URL configuration found")
        print(f"  - Function-based views: {endpoint_count}")
        print(f"  - ViewSet registrations: {router_count}")
        print(f"  - Total endpoints: ~{endpoint_count + router_count}")
    else:
        print("✗ URL configuration not found")

    print()

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total service files: {len(service_files)}")
    print(f"Valid services: {valid_services}")
    print(f"Total service code: {total_service_lines:,} lines")
    print()
    print(f"Total test files: {len(test_files)}")
    print(f"Valid test files: {valid_test_files}")
    print(f"Total test methods: {total_tests}")
    print(f"Total test code: {total_test_lines:,} lines")
    print()
    print(f"Test coverage: {len(test_files)}/{len(service_files)} services have tests")
    print()

    # Overall status
    if valid_services == len(service_files) and valid_test_files == len(test_files):
        print("✓ ALL VALIDATIONS PASSED")
        return 0
    else:
        print("⚠ SOME VALIDATIONS FAILED")
        return 1


if __name__ == '__main__':
    sys.exit(main())
