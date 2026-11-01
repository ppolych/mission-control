"""Publication faults and cooperative locking in disposable directories."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))

class ReleasePublication(unittest.TestCase):
    def test_second_replace_failure_restores_old_pair(self):
        import package_release, release_publish
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);target=root/'out.zip';sidecar=root/'out.zip.sha256'
            target.write_bytes(b'old zip');sidecar.write_bytes(b'old checksum')
            original=release_publish.os.replace
            def fail(source,destination):
                if Path(destination)==sidecar:raise OSError('injected checksum failure')
                return original(source,destination)
            with patch.object(sys,'argv',['package_release','--output',str(target)]), \
                 patch.object(release_publish.os,'replace',side_effect=fail):
                with self.assertRaises(OSError):package_release.main()
            self.assertEqual(target.read_bytes(),b'old zip')
            self.assertEqual(sidecar.read_bytes(),b'old checksum')

    def test_existing_publisher_lock_refuses_without_replacement(self):
        import package_release, release_publish
        from mission_control.storage import persistent_lock
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);target=root/'out.zip';target.write_bytes(b'old')
            with persistent_lock(root/'.out.zip.publish.lock'), \
                 patch.object(sys,'argv',['package_release','--output',str(target)]):
                with self.assertRaises(OSError):package_release.main()
            self.assertEqual(target.read_bytes(),b'old')

    def test_failed_rollback_retains_recovery_bytes(self):
        import package_release, release_publish
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);target=root/'out.zip';sidecar=root/'out.zip.sha256'
            target.write_bytes(b'old zip');sidecar.write_bytes(b'old checksum')
            original=release_publish.os.replace
            def fail(source,destination):
                if Path(destination)==sidecar or Path(source).name.startswith('previous-'):
                    raise OSError('injected publication and rollback failure')
                return original(source,destination)
            with patch.object(sys,'argv',['package_release','--output',str(target)]), \
                 patch.object(release_publish.os,'replace',side_effect=fail):
                with self.assertRaises(OSError):package_release.main()
            backups=list(root.glob('.mission-package-*/previous-0'))
            self.assertEqual(len(backups),1)
            self.assertEqual(backups[0].read_bytes(),b'old zip')
