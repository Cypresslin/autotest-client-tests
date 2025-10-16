#!/usr/bin/python3
import os
import re
import shutil
import subprocess
import unittest


class TestRevocationList(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # On Ubuntu Core, please be careful when using /etc/os-release, as the cotent will be
        # affected by the base snap of our tool (e.g. you will see Core22 on an UC16 system).
        # But here we're just using it to check if we are runnig on a UC system, so it should be fine
        with open('/etc/os-release', 'r') as fh:
            content = fh.read()

        config_file = "/boot/config-" + os.uname()[2]
        if 'Ubuntu Core' in content:
            snap_list = " ".join(os.listdir("/snap"))
            pattern = r"\w+-kernel"
            snap_pkg = re.search(pattern, snap_list).group(0)
            config_file = "/snap/{}/current/config-{}".format(snap_pkg, os.uname()[2])

        revocation_list_available = False
        with open(config_file) as f:
            for line in f:
                if re.search("CONFIG_SYSTEM_REVOCATION_KEYS", line):
                    revocation_list_available = True
                    break
        if not revocation_list_available:
            raise unittest.SkipTest("CONFIG_SYSTEM_REVOCATION_KEYS not available")

        if not shutil.which("keyctl"):
            raise unittest.SkipTest("keyutils not installed")

    def test_revocations(self):
        revocations = subprocess.check_output(
            ["keyctl", "list", "%:.blacklist"], universal_newlines=True
        )
        patterns = [
            ".* asymmetric: Canonical Ltd. Secure Boot Signing: 61482aa2830d0ab2ad5af10b7250da9033ddcef0",
        ]
        for pattern in patterns:
            with self.subTest(pattern=pattern):
                self.assertIsNotNone(re.search(pattern, revocations))


if __name__ == "__main__":
    unittest.main(verbosity=2)
