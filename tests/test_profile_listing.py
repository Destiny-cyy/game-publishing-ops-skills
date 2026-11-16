import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = (
    ROOT / "skills" / "F-校验与计算" / "plan-lint" / "scripts" / "lint_plan.py",
    ROOT / "skills" / "F-校验与计算" / "prize-calc" / "scripts" / "prize_calc.py",
)


class ProfileListingTest(unittest.TestCase):
    def test_profile_listing_commands_load_shared_profiles(self):
        for script in SCRIPTS:
            with self.subTest(script=script.name):
                result = subprocess.run(
                    [sys.executable, str(script), "--list-profiles"],
                    cwd=script.parent,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("channel_prebook", result.stdout)


if __name__ == "__main__":
    unittest.main()
