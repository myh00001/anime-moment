# Cloud DeepSeek Flash reports

The upper-left settings panel keeps the AI report on/off switch and adds a
report source: local InternVL3 + Qwen3, or the official DeepSeek Flash API.
Existing saved settings without `report_provider` continue to use local models.
The selection is frozen with the other options when a photo is captured.

Choose **云端 API · DeepSeek Flash**, enter the API Key, optionally press
**测试连接**, then use the panel's bottom save button. Blank input preserves a
previously stored key. **删除已存 Key** removes it immediately. The connection
check sends a tiny text request, without a camera image, and can incur API
usage. The cloud controls are hidden in local mode. Disabling AI reporting
prevents all report-generation API calls.

Cloud generation sends the saved **camera original**, not the anime preview,
directly to `https://api.deepseek.com/chat/completions`, with model
`deepseek-flash`. It preserves the original aspect ratio and caps the long edge
at 1536 pixels before JPEG upload. Image detail is `high`; thinking is disabled,
and output is bounded to 240 tokens with a 10-second HTTP timeout. The model
receives the campus festival background and instructions to describe visible
pose, expression, actions or surroundings conservatively, then connect them to
the AI photo experience. It does not require local image recognition first.

The existing frozen-preview/waiting animation, capture lock, A5 layout, photo
wall and print selection are retained. Missing keys, authentication failures,
network errors, rate limits and invalid/incomplete output use the existing
fallback newspaper copy. Cloud requests are not automatically retried or
silently switched to a cold local model. The record includes only the provider,
model, elapsed time, generated text or a redacted failure reason.

Keys are stored separately in `service/report-secrets.json` in a source checkout
or `report-secrets.json` beside the installed app. On Linux the file is atomically
written with mode 0600. This is owner-readable local storage, not encryption.
Keys are never included in ordinary settings JSON, capture records, PDFs, logs,
process arguments or source control. Credential files and write temporaries are
ignored by Git. Redirects and environment proxy forwarding are disabled for
credential-bearing requests.

Validation: nine focused unit tests cover direct original-image pixels, exact
model/disabled thinking, provider routing, credential separation, missing keys,
redacted non-retried errors, incomplete replies and image-free connection tests.
The twelve existing festival integration/settings tests pass. An isolated GTK
panel check on S100 verified source selection, saving, masked credentials and
clearing. A simulated API integration on the board exercised original pixels
through Chinese report generation to an actual A5 PDF, without network calls
or printing. The normal app was deployed with its local source and print/AI
settings preserved. A real authenticated cloud request remains to be checked
after the operator enters their key.

Official interface references, checked 2026-10-24:

- https://api-docs.deepseek.com/quick_start/pricing
- https://api-docs.deepseek.com/guides/vision
- https://api-docs.deepseek.com/api/create-chat-completion
