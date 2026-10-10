---
updatedAt: 2026-06-29T14:06:50.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Pro Upscaler Creative

This guide shows how to upscale images using the Pro Upscaler Creative model via the Leonardo.AI REST API.

This guide shows how to upscale images using the Pro Upscaler Creative model via the Leonardo.AI REST API.

To learn about the benefits and best practices of this upscaler, please refer to <Anchor target="_blank" href="https://leonardo.ai/news/upscale-ai-generated-images/">this blog</Anchor>.

# Sample Request

```curl
curl --location 'https://cloud.leonardo.ai/api/rest/v2/generations' \
     --header 'authorization: Bearer {api-key}' \
     --header 'Content-Type: application/json' \
     --data '{
       "model": "aurora-upscaler-creative",
       "public": false,
       "parameters": {
         "height": 848,
         "width": 1264,
         "upscale_factor": 2,
         "creativity": "low",
         "guidances": {
           "image_reference": [
             {
               "image": {
                 "id": "f823926a-ce29-4680-a599-e8af39db91b1",
                 "type": "GENERATED"
               }
             }
           ]
         }
       }
     }'
```

# Recipes

<Recipe slug="use-pro-upscaler-creative-on-generated-and-variation-images" title="Use Pro Upscaler Creative on Generated and Variation Images" />

<Recipe slug="use-pro-upscaler-precise-on-uploaded-image" title="Use Pro Upscaler Precise on Uploaded Image" />

# API Request Endpoint, Headers, Parameters

## Endpoint

```curl
https://cloud.leonardo.ai/api/rest/v2/generations
```

## Headers

```curl
--header "accept: application/json" \
--header "authorization: Bearer <YOUR_API_KEY>" \
--header "content-type: application/json"
```

## Body Parameters

| Parameter                             | Type      | Definition                                                                                                                                   |
| :------------------------------------ | :-------- | :------------------------------------------------------------------------------------------------------------------------------------------- |
| height                                | `integer` | *Required.* Height of input image in pixels.                                                                                                 |
| model                                 | `string`  | *Required.* Set to `aurora-upscaler-precise`.                                                                                                |
| parameters.upscale\_factor            | `integer` | *Required.* Controls Upscale Multiplier. Set to `2`, `3`, `4`, `5`, `6`, or `8`.                                                             |
| parameters.creativity                 | `string`  | *Required.* Controls Creativity Strength. Set to `low` for Subtle, `mid` for Balanced, or `high` for Strong.                                 |
| parameters.guidances.image\_reference | `array`   | *Required.* Array of 1 image to upscale. Each each image specifies an image.id and an image.type (`GENERATED` or `UPLOADED` or `VARIATION`). |
| public                                | `boolean` | *Optional.* Set to `false` to keep result private.                                                                                           |
| width                                 | `integer` | *Required.* Width of input image in pixels.                                                                                                  |

<br />