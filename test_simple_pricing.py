import sys
import collect

sys.stdout.reconfigure(encoding='utf-8')

samples = [
    ("grew from $160k/mo to $315k/mo in a year", []),
    ("What's your budget range? < $5k $5k - $15k", []),
    ("Starting $990", ["Starting $990"]),
    ("$50 per hour", ["$50 per hour"]),
    ("Starting at ₹10,000", ["Starting at ₹10,000"]),
]

for text, expected in samples:
    res = collect.extract_pricing(text)
    print(f"Text: {text}")
    print(f"  Result: {res}")
