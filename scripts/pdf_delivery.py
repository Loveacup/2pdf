"""Stage PDF output beside its target and publish only a successful artifact."""
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path


class DeliveryError(RuntimeError):
    """The staged PDF did not meet the requested delivery gate."""


@contextmanager
def staged_pdf(target, source, verify=False, strict=False, required_text=()):
    target = Path(target)
    # Same filesystem makes replace atomic. This is PDF delivery, not a resource sandbox.
    with tempfile.TemporaryDirectory(prefix=".2pdf-stage-", dir=target.absolute().parent) as tmp:
        staged = Path(tmp) / target.name
        yield staged
        try:
            with staged.open("rb") as stream:
                magic = stream.read(5)
            if magic != b"%PDF-" or staged.stat().st_size < 1024:
                raise DeliveryError("Staged artifact is not a complete PDF")
        except OSError as exc:
            raise DeliveryError(f"PDF generation did not produce a readable artifact: {exc}") from exc
        if verify or strict or required_text:
            command = [sys.executable, str(Path(__file__).with_name("verify_pdf.py")),
                       str(staged), "--src", str(source)]
            if strict:
                command.append("--strict")
            for text in required_text:
                command.extend(("--require-text", text))
            result = subprocess.run(command, check=False)
            if result.returncode != 0:
                raise DeliveryError(f"PDF verification failed (exit {result.returncode}); target unchanged")
        staged.replace(target)
