# Experimental queue validation

Five focused local tests passed: completed request replay suppression, interrupted claim suppression, changed input under a reused ID rejection, missing-secret no-call behavior, and extra request fields rejection. Fixtures are synthetic and no provider call was made by these tests.

The source is a standalone experimental transport; core KPP runtime and generated release files were not changed. The full core suite, doctor, smoke, and shared export checks were not run for this transport-only branch. Live Actions execution, secret validity, connector-trigger behavior and result publication remain untested. Workflow installation is pending explicit approval after automatic review blocked persistent secret access and contents-write permission. This is not a production or privacy qualification.
