---
updatedAt: 2026-09-02T14:24:09.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Remove bg

This guide shows how to remove image backgrounds using the Remove bg model via the Leonardo.AI REST API.

Leonardo provides two ways to call this model:

* **Sync API** (recommended for single images). A single request returns the processed image in the response. No polling is required. The request may take up to \~27 seconds before the service times out, so use the Async API for workloads that may exceed this.
* **Async API**. Submit a job, then retrieve the result when it completes. Suited to batch processing, very large images, and pipelines that should not hold a connection open.

The request body is identical between the two — the same `model`, `parameters`, and image reference — except that `ephemeral` and `base64` are only available on the Sync API. Unknown keys under `parameters` are rejected, not ignored.

<br />

# Sample Request

## Sync API

```curl
curl --location 'https://cloud.leonardo.ai/api/rest/v2/generationssync' \
     --header 'authorization: Bearer {api-key}' \
     --header 'Content-Type: application/json' \
     --data '{
       "model": "remove-bg",
       "public": false,
       "ephemeral": true,
       "parameters": {
         "size": "auto",
         "type": "auto",
         "format": "png",
         "guidances": {
           "image_reference": [
             {
               "image": {
                 "id": "YOUR_IMAGE_ID",
                 "type": "UPLOADED"
               }
             }
           ]
         }
       }
     }'
```

## Async API

```curl
curl --location 'https://cloud.leonardo.ai/api/rest/v2/generations' \
     --header 'authorization: Bearer {api-key}' \
     --header 'Content-Type: application/json' \
     --data '{
       "model": "remove-bg",
       "public": false,
       "parameters": {
         "size": "auto",
         "type": "auto",
         "format": "png",
         "guidances": {
           "image_reference": [
             {
               "image": {
                 "id": "YOUR_IMAGE_ID",
                 "type": "UPLOADED"
               }
             }
           ]
         }
       }
     }'
```

# API Request Endpoint, Headers, Parameters

## Endpoint

**Sync API** — the response contains the processed image (a `url` by default, or `dataB64` when `base64` is `true`). The request may take up to \~27 seconds before the service times out:

```curl
https://cloud.leonardo.ai/api/rest/v2/generationssync
```

**Async API** — the response returns a generation ID immediately; retrieve the generation by ID when it completes, or configure a webhook callback URL to receive results without polling:

```curl
https://cloud.leonardo.ai/api/rest/v2/generations
```

## Headers

Both endpoints use the same headers:

```curl
--header "accept: application/json" \
--header "authorization: Bearer <YOUR_API_KEY>" \
--header "content-type: application/json"
```

## Body Parameters

| Parameter                                         | Type      | Definition                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| :------------------------------------------------ | :-------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| base64                                            | `boolean` | *Optional. Sync API only.* When `true`, the response returns `results[].dataB64` instead of `results[].url`. The request fails if the encoded payload would exceed the response size limit. Defaults to `false`.                                                                                                                                                                                                                                        |
| ephemeral                                         | `boolean` | *Optional. Sync API only.* When `true`, the result is not persisted to your Leonardo library and the response URL is a 30-minute presigned GET. Defaults to `false`.                                                                                                                                                                                                                                                                                    |
| model                                             | `string`  | *Required.* Set to `remove-bg`.                                                                                                                                                                                                                                                                                                                                                                                                                         |
| parameters.bg\_color                              | `string`  | *Optional.* Adds a solid background colour to the cutout, as a hex code or colour name. The output is no longer transparent — pair with the `jpg` format when possible.                                                                                                                                                                                                                                                                                 |
| parameters.channels                               | `string`  | *Optional.* Set to `rgba` to return the cutout image, or `alpha` to return only the greyscale alpha mask. Defaults to `rgba`.                                                                                                                                                                                                                                                                                                                           |
| parameters.crop                                   | `boolean` | *Optional.* Set to `true` to crop the output image to the bounding box of the subject. Defaults to `false`.                                                                                                                                                                                                                                                                                                                                             |
| parameters.crop\_margin                           | `string`  | *Optional.* Margin to add around the cropped subject, as an absolute value (`30px`) or relative to the subject size (`10%`). Accepts one, two, or four values. Only applies when `crop` is enabled.                                                                                                                                                                                                                                                     |
| parameters.format                                 | `string`  | *Optional.* Output image format. Set to `png`, `jpg`, or `webp`. PNG and WebP preserve transparency, JPG does not. PNG output is capped at 10 megapixels, so pair larger `size` values with `webp` to keep transparency. Defaults to `png`.                                                                                                                                                                                                             |
| parameters.guidances.background\_image\_reference | `array`   | *Optional.* Array of exactly 1 image to composite behind the cutout, replacing the removed background. Omit to keep the background transparent (or use a solid colour via `bg_color`). Each item specifies an `image` object in the same shape as `image_reference`.                                                                                                                                                                                    |
| parameters.guidances.image\_reference             | `array`   | *Required.* Array of exactly 1 image to remove the background from. Each item specifies an `image` object with a `type` (`UPLOADED`, `GENERATED`, `VARIATION`, `URL`, or `BASE64`) plus the matching source field: `id` for images already in your Leonardo library, `url` (an image URL or base64 data URL) when `type` is `URL`, or `data` (base64-encoded image bytes) when `type` is `BASE64`. An optional `order` integer sets the guidance order. |
| parameters.position                               | `string`  | *Optional.* Position of the subject within the output canvas, as `original`, `center`, a single percentage, or two percentages for horizontal and vertical placement.                                                                                                                                                                                                                                                                                   |
| parameters.quantity                               | `integer` | *Optional.* Number of outputs to generate. Fixed at `1`. Defaults to `1`.                                                                                                                                                                                                                                                                                                                                                                               |
| parameters.roi                                    | `string`  | *Optional.* Region of interest to search for the subject, given as two x/y coordinate pairs in pixels (`0px 0px 100px 100px`) or percentages (`0% 0% 100% 100%`). Anything outside this rectangle is treated as background.                                                                                                                                                                                                                             |
| parameters.scale                                  | `string`  | *Optional.* Scale of the subject relative to the output canvas, as `original` or a percentage between `10%` and `100%`.                                                                                                                                                                                                                                                                                                                                 |
| parameters.semitransparency                       | `boolean` | *Optional.* Preserves semi-transparent regions such as glass, smoke, and veils. Defaults to `true`.                                                                                                                                                                                                                                                                                                                                                     |
| parameters.shadow\_opacity                        | `integer` | *Optional.* Opacity of the artificial shadow, from `0` to `100`. Only applies when a shadow is enabled.                                                                                                                                                                                                                                                                                                                                                 |
| parameters.shadow\_type                           | `string`  | *Optional.* Style of artificial shadow to render under the subject. Set to `none`, `drop`, `3d`, or `car`. Defaults to `none`.                                                                                                                                                                                                                                                                                                                          |
| parameters.size                                   | `string`  | *Optional.* Maximum output image resolution. Set to `auto`, `preview`, `full`, or `50MP`. PNG output is capped at 10 megapixels regardless of this setting. Defaults to `auto`.                                                                                                                                                                                                                                                                         |
| parameters.type                                   | `string`  | *Optional.* Foreground type hint to improve cutout quality. Set to `auto`, `person`, `product`, `car`, `animal`, `graphic`, `transportation`, or `other`. Defaults to `auto`.                                                                                                                                                                                                                                                                           |
| parameters.type\_level                            | `string`  | *Optional.* How specifically the subject should be classified. Set to `none` to skip classification, `1` for a coarse category, `2` for a specific category, or `latest` for the most detailed classification available.                                                                                                                                                                                                                                |
| public                                            | `boolean` | *Optional.* Set to `false` to keep result private. Ignored when `ephemeral` is `true`.                                                                                                                                                                                                                                                                                                                                                                  |

# Response

## Sync API

The Sync API always returns JSON containing the processed image.

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

| Field                                    | Definition                                                                                                             |
| :--------------------------------------- | :--------------------------------------------------------------------------------------------------------------------- |
| `id`                                     | Generation identifier. Include it when contacting support.                                                             |
| `results`                                | Array of outputs — one entry per output that passed moderation, so it can be empty. Guard your `results[0]` access.    |
| `results[0].url`                         | CDN URL of the stored image, or a 30-minute presigned URL when `ephemeral` is `true`. Omitted when `base64` is `true`. |
| `results[0].dataB64`                     | Base64-encoded image bytes. Present only when the request set `base64` to `true`.                                      |
| `results[0].contentType`                 | Media type of the generated image, e.g. `image/png`.                                                                   |
| `results[0].width` / `results[0].height` | Output dimensions in pixels, when reported by the provider.                                                            |
| `cost`                                   | Cost charged for this generation (`amount` plus a `unit` of `CREDITS` or `DOLLARS`). Present for Production API users. |
| `blockedCount`                           | Number of outputs withheld by content moderation.                                                                      |

## Async API

The Async API returns a generation ID immediately:

```json
{
  "generationId": "b3a6c1d2-…",
  "apiCreditCost": 1
}
```

| Field           | Definition                                                                                          |
| :-------------- | :-------------------------------------------------------------------------------------------------- |
| `generationId`  | The unique identifier for the generation job. Retrieve the generation by this ID when it completes. |
| `apiCreditCost` | API credit cost for the generation. Available for Production API users.                             |

Retrieve the generation by ID when it completes — persisted results include durable CDN URLs — or configure a webhook callback URL to receive real-time generation results instead of polling.