"""Private same-filesystem staging and process-owned, nonblocking target ownership."""
import hashlib
import os
import signal
import subprocess
import sys
import tempfile
import threading
import unicodedata
from contextlib import contextmanager
from pathlib import Path


class DeliveryError(RuntimeError):
    """The invocation cannot own or safely publish its target."""


@contextmanager
def target_ownership(target):
    # Resolve symlinks and case folding before naming the kernel-held lock. Lock files
    # contain no ownership state: an unlocked inode never blocks a later invocation.
    resolved = Path(target).resolve()
    key = os.path.normcase(str(resolved))
    if sys.platform == 'darwin':
        # APFS/HFS normalization is insensitive; case sensitivity is per volume.
        key = unicodedata.normalize('NFD', key)
        alternate = Path(str(resolved.parent).swapcase())
        try:
            if alternate != resolved.parent and alternate.samefile(resolved.parent):
                key = key.casefold()
        except OSError:
            pass
    digest = hashlib.sha256(key.encode()).hexdigest()
    lock_dir = Path(tempfile.gettempdir()) / '2pdf-output-locks'
    lock_dir.mkdir(mode=0o700, exist_ok=True)
    with (lock_dir / digest).open('a+b') as lock:
        try:
            if os.name == 'nt':
                import msvcrt
                if lock.tell() == 0:
                    lock.write(b'\0')
                    lock.flush()
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise DeliveryError(f'Output is already owned by another invocation: {target}') from exc
        try:
            yield
        finally:
            if os.name == 'nt':
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


@contextmanager
def handled_cancel():
    previous = None
    if threading.current_thread() is threading.main_thread():
        previous = signal.getsignal(signal.SIGTERM)
        def cancel(signum, frame):
            raise KeyboardInterrupt('render cancelled')
        signal.signal(signal.SIGTERM, cancel)
    try:
        yield
    finally:
        if previous is not None:
            signal.signal(signal.SIGTERM, previous)


def run_render_process(command, **kwargs):
    # A separate group lets cancellation stop only this invocation's Node/browser
    # children, never another renderer or a user's existing browser session.
    kwargs['start_new_session'] = os.name != 'nt'
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs) as process:
        try:
            stdout, stderr = process.communicate(timeout=180)
        except BaseException:
            if os.name != 'nt':
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            else:
                process.terminate()
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
            raise
        return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


@contextmanager
def staged_output(target, source, fmt='pdf', verify=False, strict=False, required_text=()):
    target = Path(target).resolve()
    with handled_cancel(), target_ownership(target):
        with tempfile.TemporaryDirectory(prefix='.2pdf-stage-', dir=target.parent) as tmp:
            staged = Path(tmp) / target.name
            yield staged
            try:
                with staged.open('rb') as stream:
                    magic = stream.read(8)
                if fmt == 'pdf':
                    valid = magic.startswith(b'%PDF-') and staged.stat().st_size >= 1024
                elif fmt == 'png':
                    valid = magic == b'\x89PNG\r\n\x1a\n'
                else:
                    text = staged.read_text(encoding='utf-8')
                    valid = '<html' in text and '</html>' in text
                if not valid:
                    raise DeliveryError(f'Staged artifact is not a complete {fmt}')
            except OSError as exc:
                raise DeliveryError(f'Generation did not produce a readable artifact: {exc}') from exc
            if fmt == 'pdf' and (verify or strict or required_text):
                command = [sys.executable, str(Path(__file__).with_name('verify_pdf.py')),
                           str(staged), '--src', str(source)]
                if strict:
                    command.append('--strict')
                for text in required_text:
                    command.extend(('--require-text', text))
                result = subprocess.run(command, check=False)
                if result.returncode != 0:
                    raise DeliveryError(f'PDF verification failed (exit {result.returncode}); target unchanged')
            staged.replace(target)


@contextmanager
def staged_pdf(target, source, verify=False, strict=False, required_text=()):
    with staged_output(target, source, 'pdf', verify, strict, required_text) as staged:
        yield staged
