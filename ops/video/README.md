# Video export milestone verification

The public Render deployment keeps video export disabled. This directory
contains local validation helpers for the isolated video pipeline.

## M1 verification on Windows

Start Docker Desktop, then run from the repository root:

```powershell
.\ops\video\verify-m1.ps1
```

After the images have already been built, the faster repeat command is:

```powershell
.\ops\video\verify-m1.ps1 -SkipBuild
```

The verifier:

1. validates the Compose `video` profile;
2. builds the Python 3.12 Worker and no-network Sandbox images;
3. runs export lease, isolation, quota and failure-recovery tests;
4. renders the golden Manim fixtures into real MP4 files with networking disabled.

Disposable validation secrets are scoped to the script process and removed in
the `finally` block. The script does not start the application stack, change the
public Render service, or enable public video export.
