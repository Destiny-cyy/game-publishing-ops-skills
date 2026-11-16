import os
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "F-校验与计算" / "prize-calc" / "scripts" / "prize_calc.py"


class PrizeCalcConsoleTest(unittest.TestCase):
    def test_demo_does_not_crash_on_cp936_console(self):
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "cp936"
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--demo"],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr.decode("cp936", errors="replace"))


if __name__ == "__main__":
    unittest.main()
