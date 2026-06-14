# Reporting Specification

The provisioner must compile all evidence into a markdown artifact `MISSION_TEST_REPORT.md` containing:

* **Status Table:** Showing which components passed/failed.
* **Latency Profile:** Capturing the transit time (in ms) from strategist trigger to scribe queue storage.
* **Vault Clearance Summary:** Listing what certificates and credentials were read.
* **Raw Logs Snippets:** Attaching log output for any warning or failure vectors.
