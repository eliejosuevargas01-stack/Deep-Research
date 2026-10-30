# Native image attachment verification

The official installed Hermes CLI `chat --oneshot -Q --image <path>` was used with the isolated temporary native-image profile, primary `ag/gemini-3.8-flash-high`, 9router and reasoning high. No auxiliary vision model was configured or used.

Session `20261026_152318_2a0fb5` completed with zero tools. It correctly identified the white background, violet buttons, left preferences panel, exact controls, selected four personas, and demo topic from the approved screenshot. This resolves the earlier failures: a path in `-z` is not an attachment; native tool-image routing alone was not proven. Future visual reviews must use an explicit primary user-image attachment, not assume tool-image delivery.

Image: evidence/hermes-browser-capability/hermes-browser-capability.png
SHA256: 67aeb54563d35d7c040f52ddadc561b991d7af0bfbad1a41926beb5313a40e40

Original user Hermes configuration was not modified. Temporary profile is private and must be removed once all review work has completed. The earlier source/DOM round remains provisional and does not retroactively become a fully visual round.

Verified at 2026-10-26T18:25:07.475254+00:00
