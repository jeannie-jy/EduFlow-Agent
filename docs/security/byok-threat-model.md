# BYOK credential security boundary

EduFlow supports only fixed `deepseek` and `dashscope` provider identifiers.
Users cannot supply endpoints, hosts, models, headers, or proxy settings. This is
the SSRF boundary and must remain enforced server-side.

Each API key is encrypted with a random data-encryption key using AES-256-GCM.
The data key is separately wrapped by the configured 256-bit key-encryption key;
user/provider/purpose/version are authenticated as AAD. Persistent records expose
only a keyed fingerprint and the last four characters. There is no plaintext
read endpoint.

Plaintext may exist only in an API or credentialed worker memory while creating
an outbound provider client. It must never enter logs, exception payloads,
project snapshots, background payloads, SSE events, workflow checkpoints, traces,
Redis or object storage. Background jobs persist only credential ID and version;
revoked versions fail closed.

`local` mode uses `CREDENTIAL_KEK_B64` only for development. Staging and
production refuse to start unless `CREDENTIAL_KMS_BACKEND=http`: the API and
credentialed worker send a data key plus AAD to a fixed internal HTTPS KMS
Bridge and persist only the returned wrapped key. The Bridge is responsible for
using the selected cloud KMS, authenticating the caller, applying separate
wrap/unwrap policy, and emitting provider-native access audit logs. Its bearer
identity and the independent fingerprint HMAC key come from Secret Manager.
KMS errors fail closed and are never retried with the local KEK.

The Bridge exposes two authenticated JSON endpoints on the private service
network. `wrap` accepts `plaintext_b64`, `aad_b64`, and the requested
`key_version`, then returns `ciphertext_b64` and the authoritative
`key_version`. `unwrap` accepts `ciphertext_b64`, `aad_b64`, and the stored
`key_version`, then returns `plaintext_b64`. It must reject unknown callers,
non-TLS traffic, altered AAD and unauthorized key versions; responses and
request bodies must never be logged. API and worker identities may call only
these operations, while migration, render and material-sandbox identities have
no permission.

Rotate stored credential envelopes before retiring an old KMS key version.
Server-side BYOK is not end-to-end encryption: EduFlow can decrypt a key to
perform the requested call, which is disclosed in the product privacy notice.
