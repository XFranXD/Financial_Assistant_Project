import sys
sys.path.insert(0, '.')
from analyzers.expectations import get_expectations_signal

r = get_expectations_signal('TEST', '', 15.0, [1.0, 1.5, 1.2, 1.8, 1.1, 1.3, 1.4, 1.6])
print("Test C returned:", r)
