---
updatedAt: 2026-09-02T14:27:08.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Migrate from the remove.bg API to Leonardo.Ai

Background removal is now available through the Leonardo.Ai API. This guide describes the differences between the two APIs and the code changes required to migrate.

Leonardo provides two options:

* <Anchor target="_blank" href="https://docs.leonardo.ai/docs/remove-bg#sync-api">**Sync API**</Anchor> (recommended for remove.bg migrations). A single request returns the processed image in the response. No polling is required. This guide focuses on the Sync API.
* <Anchor target="_blank" href="https://docs.leonardo.ai/docs/remove-bg#async-api">**Async API**</Anchor>**.** Submit a job, then retrieve the result when it completes. Suited to batch processing, very large images, and pipelines that should not hold a connection open. See docs on the Async API.

## What changes at a glance

|                                        | Remove.bg API                                             | Leonardo Sync API                                                                                                                      |
| -------------------------------------- | --------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| **Endpoint**                           | `POST https://api.remove.bg/v1.0/removebg`                | `POST https://cloud.leonardo.ai/api/rest/v2/generationssync`                                                                           |
| **Auth**                               | `X-Api-Key: <key>`                                        | `Authorization: Bearer <LEONARDO_API_KEY>`                                                                                             |
| **Request body**                       | `multipart/form-data` or JSON                             | JSON only (`application/json`)                                                                                                         |
| **Model**                              | Implicit                                                  | Explicit: `"model": "remove-bg"`                                                                                                       |
| **Source image**                       | `image_file` / `image_url` / `image_file_b64` form fields | One `image` object inside `parameters.guidances.image_reference`: URL, base64, or an uploaded image ID                                 |
| **Max input size**                     | 22MB                                                      | Input URL / BASE64 / upload: up to 25MB. <br />Output `dataB64` (only if `"base64": true`): under \~7.45MB of pixels or the call fails |
| **Options (size, type, bg\_color, …)** | Top-level form fields                                     | Same names, nested under `parameters`                                                                                                  |
| **Response**                           | Raw image bytes by default (JSON optional)                | Always JSON. Default: `results[0].url`. <br />With `"base64": true`: `results[0].dataB64` (no `url`)                                   |
| **Result storage**                     | Nothing kept                                              | Kept in your Leonardo library by default: set `ephemeral: true` → 30-minute URL, nothing in the library                                |
| **Output formats**                     | png, jpg, webp, zip, auto                                 | png, jpg, webp (no zip, no auto)                                                                                                       |
| **Cost reporting**                     | `X-Credits-Charged` header                                | `cost` object in the response body (USD $)                                                                                             |

Three changes cover most integrations:

1. New endpoint and auth header.
2. The request becomes JSON. File uploads are base64-encoded; option values are unchanged and move under `parameters`.
3. The response is JSON. Default: download `results[0].url`. To get bytes in the response, set `"base64": true` and decode `results[0].dataB64`.

## Before you start

You will need a Leonardo account with API access. Create an API key from the API Access page at [app.leonardo.ai](https://app.leonardo.ai) and send it as a Bearer token on every request.

Background removal costs USD $0.1047 per image. Each response includes the cost of the call. Current pricing: <https://app.leonardo.ai/api-access/pricing-calculator>

## The five-minute migration

**Before**, remove.bg with an image URL:

```curl
curl -H 'X-Api-Key: YOUR_KEY' \
  -F 'image_url=https://www.remove.bg/example.jpg' \
  -F 'size=auto' \
  -f https://api.remove.bg/v1.0/removebg -o no-bg.png
```

**After**, Leonardo Sync:

```curl
curl --request POST \
  --url https://cloud.leonardo.ai/api/rest/v2/generationssync \
  --header 'accept: application/json' \
  --header 'authorization: Bearer YOUR_LEONARDO_API_KEY' \
  --header 'content-type: application/json' \
  --data '{
    "model": "remove-bg",
    "ephemeral": true,
    "parameters": {
      "size": "full",
      "format": "png",
      "guidances": {
        "image_reference": [
          { "image": { "type": "URL", "url": "https://www.remove.bg/example.jpg" } }
        ]
      }
    }
  }' | jq -r '.results[0].url'
```

The flow is unchanged: a single request returns the image. The two structural differences are that the source image and options move into a JSON body, and the output is JSON. Default is a URL; set `"base64": true` if you want bytes in the body.

## Common integration scenarios

Find your current integration below for the specific changes that apply to you.

| Your integration today                  | Where to look                                                                                                                    |
| --------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `image_url` in, image file (binary) out | [Scenario 1](https://docs.leonardo.ai/docs/migrate-from-the-removebg-api-to-leonardoai#scenario-1-image-url-in-image-file-out)   |
| `image_file` upload in, image file out  | [Scenario 2](https://docs.leonardo.ai/docs/migrate-from-the-removebg-api-to-leonardoai#scenario-2-file-upload-in-image-file-out) |
| `image_file_b64` in, JSON out           | [Scenario 3](https://docs.leonardo.ai/docs/migrate-from-the-removebg-api-to-leonardoai#scenario-3-base64-in-json-out)            |
| `format=zip` output                     | [Scenario 4](https://docs.leonardo.ai/docs/migrate-from-the-removebg-api-to-leonardoai#scenario-4-zip-output)                    |
| `bg_image_file`                         | [Scenario 5](https://docs.leonardo.ai/docs/migrate-from-the-removebg-api-to-leonardoai#scenario-5-background-image-replacement)  |

### Scenario 1: image URL in, image file out

This is the request shown in the five-minute migration above. What to change and be aware of:

1. The URL moves from the `image_url` form field to `parameters.guidances.image_reference[0].image` with `"type": "URL"`.
   * HTTPS URLs only; Leonardo fetches images up to \~20MB.
2. The response is JSON, not raw bytes. Default: GET `results[0].url` (30-minute link when `ephemeral: true`). For inline bytes, add `base64: true` and decode `results[0].dataB64`.
3. If you use `format=auto` today, set a format explicitly: `png` or `webp` for transparency, `jpg` otherwise.
4. Set `"ephemeral": true` to match remove.bg's behaviour of not storing your images. By default, results are saved to your Leonardo library.
5. The cost of each call is in the response body rather than the `X-Credits-Charged` header.

**Example response**

Default result `url`:

```json
{
  "id": "b3a6c1d2-…",
  "blockedCount": 0,
  "cost": { "amount": "0.1047", "unit": "DOLLARS" },
  "results": [
    {
      "url": "https://…",
      "contentType": "image/png",
      "width": 1024,
      "height": 768
    }
  ]
}
```

When `base64: true` is set:

```json
{
  "id": "b3a6c1d2-…",
  "blockedCount": 0,
  "cost": { "amount": "0.1047", "unit": "DOLLARS" },
  "results": [
    {
      "dataB64": "iVBOR…",
      "contentType": "image/png",
      "width": 1024,
      "height": 768
    }
  ]
}
```

Write the image to disk:

```bash
# Default (url)
curl … | jq -r '.results[0].url'

# With "base64": true
curl … | jq -r '.results[0].dataB64' | base64 --decode > no-bg.png
```

### Scenario 2: file upload in, image file out

The Sync API does not accept `multipart/form-data`, so files cannot be attached directly.

For files under \~7.5MB, base64-encode the file and send it in the JSON body, a code change only, with no additional requests.

**Before**, remove.bg (Python):

```python
import requests

response = requests.post(
    'https://api.remove.bg/v1.0/removebg',
    files={'image_file': open('/path/to/file.jpg', 'rb')},
    data={'size': 'auto'},
    headers={'X-Api-Key': 'YOUR_KEY'},
)

if response.status_code == requests.codes.ok:
    with open('no-bg.png', 'wb') as out:
        out.write(response.content)
```

**After**, Leonardo Sync (Python):

```python
import base64, requests

with open('/path/to/file.jpg', 'rb') as f:
    image_b64 = base64.b64encode(f.read()).decode()

response = requests.post(
    'https://cloud.leonardo.ai/api/rest/v2/generationssync',
    headers={'Authorization': 'Bearer YOUR_LEONARDO_API_KEY'},
    json={
        'model': 'remove-bg',
        'ephemeral': True,
        'base64': True,
        'parameters': {
            'size': 'auto',
            'format': 'png',
            'guidances': {
                'image_reference': [
                    {'image': {'type': 'BASE64', 'data': image_b64}}
                ]
            }
        }
    },
)

if response.ok:
    results = response.json()['results']
    with open('no-bg.png', 'wb') as out:
        out.write(base64.b64decode(results[0]['dataB64']))
else:
    print('Error:', response.status_code, response.text)
```

**Node.js:**

```javascript
import fs from "node:fs";

const imageB64 = fs.readFileSync("/path/to/file.jpg").toString("base64");

const response = await fetch("https://cloud.leonardo.ai/api/rest/v2/generationssync", {
  method: "POST",
  headers: {
    "Authorization": "Bearer YOUR_LEONARDO_API_KEY",
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    model: "remove-bg",
    ephemeral: true,
    base64: true,
    parameters: {
      size: "auto",
      format: "png",
      guidances: {
        image_reference: [{ image: { type: "BASE64", data: imageB64 } }],
      },
    },
  }),
});

if (response.ok) {
  const { results } = await response.json();
  fs.writeFileSync("no-bg.png", Buffer.from(results[0].dataB64, "base64"));
} else {
  throw new Error(`${response.status}: ${await response.text()}`);
}
```

Be aware of:

1. Input BASE64 / URL / upload accepts images up to 25MB. That is separate from output `dataB64`, which only works for outputs under \~7.45MB of pixels. For a large output, omit `base64` and use the URL.
2. Send raw image bytes as base64, without a `data:` prefix. From a shell, `base64 -w0 file.jpg` produces the encoded string.
3. The response and storage notes from Scenario 1 apply here as well.
4. If you process the same source image repeatedly, or want inputs stored in your Leonardo library, upload once via the init-image endpoint and reference the returned ID: `{ "type": "UPLOADED", "id": "<init-image-uuid>" }`.

### Scenario 3: base64 in, JSON out

The closest match, your integration structure is unchanged. Three renames apply:

1. **Request:** `image_file_b64` becomes the `image` object `{ "type": "BASE64", "data": … }` under `parameters.guidances.image_reference`. Source images under \~7.5MB; larger files should be passed as a URL.
2. **Response:** Default: `results[0].url`. With `"base64": true`: `results[0].dataB64`.
3. **Cost:** read the `cost` object in the body instead of the `X-Credits-Charged` header.

### Scenario 4: ZIP output

The ZIP format (`color.jpg` + `alpha.png`) is not supported. Request the final format directly (`png` or `webp` for transparency) and remove the client-side composition step from your pipeline. If you consume the alpha matte separately, the `channels` parameter (`alpha`) is supported.

### Scenario 5: background image replacement

`bg_image_url` becomes `guidances.background_image_reference`: it is renamed, becomes an array of image objects, and sits under `parameters.guidances` rather than with the other options:

```json
"parameters": {
  "format": "png",
  "guidances": {
    "image_reference": [
      { "image": { "type": "URL", "url": "https://assets.leonardo.ai/xxwm-YUEYUO43E2f_example.jpg" } }
    ],
    "background_image_reference": [
      { "image": { "type": "URL", "url": "https://example.com/background.jpg" } }
    ]
  }
}
```

`bg_image_file` has no direct equivalent — background images cannot be attached or inlined in the request. Host it and pass it as `background_image_reference` (URL / BASE64 / UPLOADED). Do not send `parameters.bg_image_url`.

## The request

```json
{
  "model": "remove-bg",
  "ephemeral": true,
  "public": false,
  "parameters": {
    "format": "png",
    "size": "auto",
    "guidances": {
      "image_reference": [
        { "image": { /* one input mode */ } }
      ]
    }
  }
}
```

* `model` (required) — always `"remove-bg"`.
* `ephemeral` (optional, default `false`) — controls whether input and output are kept in your Leonardo library. See [Result storage and privacy](#result-storage-and-privacy).
* `public` (optional, default `false`) — feed visibility; only relevant when results are persisted.
* `parameters` (required) — your remove.bg options plus the source image.

Provide exactly one source per `image` object — do not mix fields:

| remove.bg field    | Leonardo `image` object                                                                                     | Size limit                                       |
| ------------------ | ----------------------------------------------------------------------------------------------------------- | ------------------------------------------------ |
| `image_url`        | `{ "type": "URL", "url": "https://assets.leonardo.ai/xxwm-YUEYUO43E2f_example.jpg" }`                       | Up to \~25MB                                     |
| `image_file_b64`   | `{ "type": "BASE64", "data": "<base64-encoded-bytes>" }`                                                    | Under \~7.5MB                                    |
| `image_file=@file` | Base64-encode the file (BASE64), or upload once and use `{ "type": "UPLOADED", "id": "<init-image-uuid>" }` | Under \~7.5MB as base64; up to \~25MB via upload |

Images already in Leonardo can also be used as sources: `UPLOADED` (uploaded images), `GENERATED` (generated images), and `VARIATION` (variation outputs).

## Parameter mapping

Option values carry over unchanged; they move under `parameters`.

| remove.bg                        | Leonardo                                               | Notes                                                                                                  |
| -------------------------------- | ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------ |
| `size`                           | `parameters.size`                                      | Same values: `preview`, `auto`, `full`, `50MP`                                                         |
| `type`                           | `parameters.type`                                      | Same subject hints: `auto`, `person`, `product`, `car`, `animal`, `graphic`, `transportation`, `other` |
| `type_level`                     | `parameters.type_level`                                | Unchanged                                                                                              |
| `format`                         | `parameters.format`                                    | `png`, `jpg`, `webp`. No `zip` or `auto`                                                               |
| `channels`                       | `parameters.channels`                                  | Unchanged (`rgba` / `alpha`)                                                                           |
| `bg_color`                       | `parameters.bg_color`                                  | Unchanged                                                                                              |
| `crop` / `crop_margin`           | `parameters.crop` / `parameters.crop_margin`           | Unchanged                                                                                              |
| `roi`                            | `parameters.roi`                                       | Unchanged                                                                                              |
| `scale` / `position`             | `parameters.scale` / `parameters.position`             | Unchanged                                                                                              |
| `semitransparency`               | `parameters.semitransparency`                          | Unchanged                                                                                              |
| `shadow_type` / `shadow_opacity` | `parameters.shadow_type` / `parameters.shadow_opacity` | Unchanged                                                                                              |
| `add_shadow`                     | —                                                      | Deprecated on remove.bg; use `shadow_type` + `shadow_opacity`                                          |
| `bg_image_url`                   | `guidances.background_image_reference`                 | Moved into `guidances`                                                                                 |
| `bg_image_file`                  | —                                                      | No equivalent — host the image and use `guidances.background_image_reference` — see Scenario 5         |

## The response

Always JSON; there is no raw-bytes response mode.

```json
{
  "id": "b3a6c1d2-…",
  "blockedCount": 0,
  "cost": { "amount": "0.1047", "unit": "DOLLARS" },
  "results": [
    {
      "contentType": "image/png",
      "url": "https://…",
      "width": 1234,
      "height": 567
    }
  ]
}
```

* `id` — request ID; include it when contacting support.
* `results` — array of outputs. Background removal returns one entry.
* `results[0].dataB64` — only when `"base64": true`.
* `results[0].url` — default path. Durable CDN if `ephemeral: false`. 30-minute S3 GET if `ephemeral: true`. Omitted when `"base64": true`.
* `results[0].contentType` — e.g. `image/png`.
* `results[0].width` / `results[0].height` — output dimensions, when available.
* `cost` — the cost of the call in USD.
* `blockedCount` — usually `0` for this model.

Where remove.bg response data maps to:

| remove.bg                                                      | Leonardo Sync                                                                          |
| -------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| Raw image bytes (default)                                      | `results[0].dataB64` — decode to bytes                                                 |
| `data.result_b64` (JSON mode)                                  | Default: download `results[0].url`. Inline: `"base64": true` then `results[0].dataB64` |
| `Content-Type` header                                          | `results[0].contentType`                                                               |
| `X-Width` / `X-Height` headers                                 | `results[0].width` / `height`                                                          |
| `X-Credits-Charged` header                                     | `cost` object in the body (USD)                                                        |
| `X-Type` (detected foreground)                                 | No equivalent                                                                          |
| `X-Foreground-Top/Left/Width/Height` (and JSON `foreground_*`) | No equivalent                                                                          |

## Result storage and privacy

The default storage behaviour differs from remove.bg. Remove.bg stores nothing; Leonardo persists the input and output to your Leonardo library and CDN by default (`ephemeral: false`).

To replicate remove.bg's behaviour, nothing kept after the call, set:

```json
"ephemeral": true
```

With `ephemeral: true`, no lasting library assets are created for input or output; the response returns a 30-minute `url`. Add `"base64": true` if you want `dataB64` instead of that `url`.

With the default `ephemeral: false`, results persist to your library with a CDN URL, and `public` controls feed visibility.

Usage is metered either way; the flag controls whether images are kept, not billing. Review this setting if you process customer images.

## Errors, rate limits, and retries

Error handling follows the same pattern: Hasura usually returns HTTP 200 with `errors[]`. Read `errors[0].message` and `extensions.statusCode` / `extensions.code` (e.g. `BAD_REQUEST`). Do not rely on HTTP 4xx alone.

## Not yet supported

| remove.bg feature                         | Status on Leonardo                                                                                                |
| ----------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| `format=zip`                              | Will not be supported. Request `png` or `webp` directly (Scenario 4)                                              |
| `format=auto`                             | Will not be supported. Set `png`, `jpg`, or `webp` explicitly                                                     |
| `bg_image_file`                           | No equivalent — host the image and use `guidances.background_image_reference` — see Scenario 5                    |
| Raw image bytes in the response           | Will not be supported. The response is always JSON. Default is a `url`; `dataB64` only with `"base64": true`      |
| `multipart/form-data` requests            | Will not be supported. JSON only; input BASE64/URL/upload up to 25MB. Output `dataB64` is a separate \~7.45MB cap |
| `X-Type` and foreground-position metadata | Will not be supported                                                                                             |
| `POST /improve` (image contribution)      | Will not be supported                                                                                             |
| OAuth 2.0 end-user login                  | Will not be supported. Authenticate with your account's API key                                                   |

## The Async API

The Sync API is the closest match to remove.bg. Leonardo's Production API also supports background removal asynchronously, which suits batch processing, very large images, and pipelines that should not hold a connection open.

The flow:

1. `POST https://cloud.leonardo.ai/api/rest/v2/generations` with the same request body as the Sync API (same model, parameters, and image reference). Do not send `ephemeral` or `base64`.
2. The response returns a generation ID immediately.
3. Retrieve the generation by ID when it completes. Persisted results include durable CDN URLs.
4. Optionally configure a webhook callback URL to receive real-time generation results instead of polling.

The request body is identical, so moving between sync and async requires minimal change. The same request format also provides access to Leonardo's other image, video, 3D, Blueprint and audio models.

## Migration checklist

1. Create a Leonardo API key and swap `X-Api-Key` for `Authorization: Bearer <key>`.
2. Point requests at `POST https://cloud.leonardo.ai/api/rest/v2/generationssync`.
3. Send `Content-Type: application/json` with `"model": "remove-bg"`.
4. Move your source image into `parameters.guidances.image_reference`: base64 for files under \~7.5MB, URL or upload + reference for larger files.
5. Move your options under `parameters`: values unchanged.
6. Replace `format=auto` / `format=zip` with an explicit `png`, `jpg`, or `webp`.
7. Download `results[0].url`, or set `"base64": true` and decode `results[0].dataB64`; read cost (USD) from `cost` instead of `X-Credits-Charged`.
8. Set `"ephemeral": true` if you require remove.bg-style no-storage behaviour.
9. Keep your 429/5xx retry logic; update error parsing to the Leonardo error shape.
10. If you use `bg_image_file` or ZIP output, review [Not yet supported](#not-yet-supported) before cutting over.