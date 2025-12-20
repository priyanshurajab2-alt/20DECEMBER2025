import os
import re

BASE_DIR = "."  # Project root

# ✅ Safe constants and values
SAFE_CONSTANT_VALUES = {
    "USER_DB_FILE": "/var/data/admin_users.db",
    "DB_FILE": "/var/data/1st_year.db",
    "GENERAL_MCQ_DB_FILE": "/var/data/general_mcq.db",
    "TEST_DB_FILE": "/var/data/test_database.db"
}

# Patterns that may be unsafe
PATTERNS = [
    r"sqlite3\.connect\(['\"][^'\"]+\.db['\"]\)",
    r"os\.path\.exists\(['\"][^'\"]+\.db['\"]\)",
    r"os\.remove\(['\"][^'\"]+\.db['\"]\)",
    r"DB_FILE\s*=\s*['\"][^'\"]+\.db['\"]",
    r"USER_DB_FILE\s*=\s*['\"][^'\"]+\.db['\"]",
    r"GENERAL_MCQ_DB_FILE\s*=\s*['\"][^'\"]+\.db['\"]",
    r"TEST_DB_FILE\s*=\s*['\"][^'\"]+\.db['\"]"
]

# Special logical case patterns
FALLBACK_DB_PATTERN = r"return\s+['\"][^'\"]+\.db['\"]"
DELETE_DB_COMPARE_PATTERN = r"db_file\s*==\s*['\"][^'\"]+\.db['\"]"

def is_safe_constant(line):
    """Return True if line matches a known safe constant/value."""
    for const, correct_val in SAFE_CONSTANT_VALUES.items():
        if const in line and correct_val in line:
            return True
    return False

def scan_file(filepath):
    issues, corrects, extras = [], [], []
    with open(filepath, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            stripped = line.strip()

            if is_safe_constant(stripped):
                corrects.append((lineno, stripped))
                continue

            # Path issues
            for pat in PATTERNS:
                if re.search(pat, stripped):
                    if "/var/data/" not in stripped:
                        issues.append((lineno, stripped))
                    else:
                        corrects.append((lineno, stripped))

            # Special cases to warn
            if re.search(FALLBACK_DB_PATTERN, stripped) and "/var/data/" not in stripped:
                extras.append(("Fallback DB path?", lineno, stripped))
            if re.search(DELETE_DB_COMPARE_PATTERN, stripped):
                extras.append(("Delete check uses full path compare — use os.path.basename()", lineno, stripped))
    return issues, corrects, extras

def main():
    any_issues = False
    any_corrects = False

    print("\n🔍 Persistent DB Path Audit\n" + "="*40)

    for root, _, files in os.walk(BASE_DIR):
        for file in files:
            if not file.endswith(".py"):
                continue
            path = os.path.join(root, file)
            issues, corrects, extras = scan_file(path)

            if corrects or issues or extras:
                print(f"\n📄 {path}")
            
            if corrects:
                any_corrects = True
                print("   ✅ Correct references:")
                for lineno, code in corrects:
                    print(f"      Line {lineno}: {code}")

            if issues:
                any_issues = True
                print("   ❌ Potential issues:")
                for lineno, code in issues:
                    print(f"      Line {lineno}: {code}")

            if extras:
                any_issues = True
                print("   ⚠ Logical warnings:")
                for msg, lineno, code in extras:
                    print(f"      {msg} at line {lineno}: {code}")

    print("\nSummary:")
    if any_corrects:
        print("   ✅ Found correct persistent DB references.")
    if not any_corrects:
        print("   ⚠ No correct references found — may indicate missing constants/paths.")
    if any_issues:
        print("   ❌ Found potential issues/warnings — review required.")
    else:
        print("   🎉 No issues found — all DB paths appear persistent-safe.")

if __name__ == "__main__":
    main()
