# Local Stage-N webMUSHRA setup

The exporter creates a study package only; the official webMUSHRA checkout remains external under the approved download directory. Copy the generated YAML into its `configs` directory and the study `audio` directory into `configs/s12-stage-n/audio`, then start its Docker Compose service.

Open `http://127.0.0.1:8000/?config=s12-stage-n.yaml` in Chrome. The built-in PHP service writes raw CSV under `results/s12-stage-n-webmushra-v1/`; normalize it with the generated SHA binding before import. The hidden reference is a synthetic parent and cannot become a real-reference or human-pass claim.
