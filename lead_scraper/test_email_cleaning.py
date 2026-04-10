"""
Test Email Cleaning - Fix Zip Code Contamination
"""

import re


def _clean_email(email):
    """Clean extracted email address from common contamination."""
    if not email:
        return None
    
    # Remove whitespace
    email = email.strip()
    
    # Split into parts
    if '@' not in email:
        return None
    
    local_part = email.split('@')[0]
    domain = email.split('@')[1].split()[0].strip()  # Get first domain part
    
    # Remove leading numbers (zip codes, etc.)
    # "79932sales" -> "sales"
    local_part = re.sub(r'^[0-9]+', '', local_part)
    
    # Remove trailing numbers
    local_part = re.sub(r'[0-9]+$', '', local_part)
    
    # Remove special characters at start/end
    local_part = local_part.strip('.,;:!?()[]{}"\' ')
    domain = domain.rstrip('.,;:!?()[]{}"\' ')
    
    # Must have both parts
    if not local_part or not domain:
        return None
    
    # Reconstruct
    cleaned = f"{local_part}@{domain}"
    
    return cleaned


def test_email_cleaning():
    """Test email cleaning fixes."""
    
    test_cases = [
        # (input, expected_output)
        ("79932sales@compound-design.com", "sales@compound-design.com"),
        ("  sales@company.com  ", "sales@company.com"),
        ("123info@test.com", "info@test.com"),
        ("contact@example.com,", "contact@example.com"),
        ("john.smith@carpentry.net", "john.smith@carpentry.net"),
        ("2026hello@test.com", "hello@test.com"),
        ("email789@company.org", "email@company.org"),
    ]
    
    print("\n" + "=" * 70)
    print("🧹 EMAIL CLEANING TEST")
    print("=" * 70)
    
    passed = 0
    failed = 0
    
    for dirty_email, expected in test_cases:
        cleaned = _clean_email(dirty_email)
        
        if cleaned == expected:
            print(f"✅ PASS")
            print(f"   Input:    {dirty_email}")
            print(f"   Output:   {cleaned}")
            print(f"   Expected: {expected}")
            passed += 1
        else:
            print(f"❌ FAIL")
            print(f"   Input:    {dirty_email}")
            print(f"   Output:   {cleaned}")
            print(f"   Expected: {expected}")
            failed += 1
        print()
    
    print("=" * 70)
    print(f"📊 RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)
    
    if failed == 0:
        print("✅ All cleaning tests passed!")
    else:
        print(f"❌ {failed} tests failed")
    print()


if __name__ == "__main__":
    test_email_cleaning()