import os
import re

BASE_DIR = "."  # Set to your project root, or use '.' for current
SAFE_CONSTANT_VALUES = {
    "USER_DB_FILE": "/var/data/admin_users.db",
    "DB_FILE": "/var/data/1st_year.db",
    "GENERAL_MCQ_DB_FILE": "/var/data/general_mcq.db",
    "TEST_DB_FILE": "/var/data/test_database.db"
}

PATTERNS = [
    r"sqlite3\.connect\(['\"][^'\"]+\.db['\"]\)",
    r"os\.path\.exists\(['\"][^'\"]+\.db['\"]\)",
    r"os\.remove\(['\"][^'\"]+\.db['\"]\)",
    r"(?:DB_FILE|USER_DB_FILE|GENERAL_MCQ_DB_FILE|TEST_DB_FILE)\s*=\s*['\"][^'\"]+\.db['\"]"
]

FALLBACK_DB_PATTERN = r"return\s+['\"][^'\"]+\.db['\"]"
DELETE_DB_COMPARE_PATTERN = r"db_file\s*==\s*['\"][^'\"]+\.db['\"]"

def is_safe_constant(line):
    for const, correct_val in SAFE_CONSTANT_VALUES.items():
        if const in line and correct_val in line:
            return True
    return False

def scan_file(filepath):
    issues, corrects, logical_warnings = [], [], []
    with open(filepath, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            stripped = line.strip()

            # Detect perfectly correct
            if is_safe_constant(stripped):
                corrects.append((lineno, stripped))
                continue

            # Path issues/potentially problematic usage
            for pat in PATTERNS:
                if re.search(pat, stripped):
                    if "/var/data/" in stripped or is_safe_constant(stripped):
                        corrects.append((lineno, stripped))
                    else:
                        issues.append((lineno, stripped))

            # Logic-level warnings
            if re.search(FALLBACK_DB_PATTERN, stripped) and "/var/data/" not in stripped:
                logical_warnings.append(("Fallback DB path needs /var/data/", lineno, stripped))
            if re.search(DELETE_DB_COMPARE_PATTERN, stripped):
                logical_warnings.append(("Unsafe delete_database() check; use os.path.basename()", lineno, stripped))
    return corrects, issues, logical_warnings

def main():
    any_errors = False
    any_corrects = False

    print("\n=========== Persistent DB Path Audit ===========\n")
    for root, _, files in os.walk(BASE_DIR):
        for file in files:
            if not file.endswith(".py"):
                continue
            filepath = os.path.join(root, file)
            corrects, issues, logical_warnings = scan_file(filepath)
            if corrects or issues or logical_warnings:
                print(f"\n📄 {filepath}\n" + "-"*60)
            if corrects:
                any_corrects = True
                print("✅ Correct persistent DB references:")
                for lineno, code in corrects:
                    print(f"   [Line {lineno}]: {code}")
            if issues:
                any_errors = True
                print("❌ Issues (unsafe DB usage):")
                for lineno, code in issues:
                    print(f"   [Line {lineno}]: {code}")
            if logical_warnings:
                any_errors = True
                print("⚠ Logical warnings:")
                for msg, lineno, code in logical_warnings:
                    print(f"   [Line {lineno} - {msg}]: {code}")

    print("\n========== Audit Summary ==========")
    if any_corrects:
        print("✅ Some correct persistent DB references found.")
    else:
        print("⚠ No correct persistent DB usage detected (possible configuration problem).")
    if any_errors:
        print("❌ One or more issues/warnings found. Fix unsafe and fallback usages before deployment.")
    else:
        print("🎉 All database paths and logic appear persistent-disk safe!")

if __name__ == "__main__":
    main()
