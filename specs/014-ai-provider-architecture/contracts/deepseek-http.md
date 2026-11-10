# Contract: DeepSeek HTTP Boundary

**Feature**: `014-ai-provider-architecture`

This is the external provider boundary used only by the Assistant and AI Actions. It is read-only advisory inference and has no tools, operational actions, refreshes, or external-system queries.

## Request

`POST {base_url}/chat/completions`

Headers:
```text
Authorization: Bearer <NOC_WEB_DEEPSEEK_API_KEY>
Content-Type: application/json
Accept: application/json
```

Body:
```json
{
  "model": "deepseek-flash",
  "messages": [
    {"role": "system", "content": "<bounded read-only advisory rules; includes the word JSON>"},
    {"role": "user", "content": "<bounded request envelope JSON>"}
  ],
  "response_format": {"type": "json_object"},
  "thinking": {"type": "disabled"},
  "stream": false,
  "temperature": 0.2,
  "max_tokens": 4096
}
```

Constants:
- Default base URL: `https://api.deepseek.com`
- Default model: `deepseek-flash`
- JSON output mode required
- No tools, tool choice, external retrieval, or operational instructions

## Response handling

The adapter accepts only:
- HTTP 200 with a JSON object.
- `choices` is a non-empty list.
- First choice `message.content` is a non-empty string after whitespace trimming.
- `finish_reason` is not `length`.
- `content` parses as a JSON object.
- The parsed object is returned to the existing Assistant validator without adding fields.

Rejected as `invalid`:
- Blank/whitespace-only content.
- `finish_reason: "length"`.
- Non-object JSON or non-JSON content.
- Invalid UTF-8.
- Response larger than 1 MiB.

Rejected as `timeout`:
- Socket/read timeout within the bounded timeout.

Rejected as `unavailable`:
- HTTP 3xx (redirects are refused), 400, 401, 402, 403, 422, 429, 500, 502, 503, 504.
- DNS, TLS, connection, or other network failure.
- Invalid/unreachable endpoint.

## Security rules

- HTTPS only; reject userinfo, query, fragment, and parent traversal in the base URL.
- Do not follow HTTP redirects; treat any 3xx response as `unavailable` so the authorization header is never forwarded to another host.
- Credential only in the `Authorization` header.
- Never log request/response bodies, headers, URLs with credentials, or upstream error text.
- Never persist prompts, raw provider output, reasoning content, or credentials.
- No automatic retry.
- No automatic fallback to another provider.
- No credentials in responses, reports, or diagnostic output.

## Provider attribution

On success or controlled failure, the Assistant attributes the response to `deepseek-api`. The model identifier is not part of the provider identity field.
