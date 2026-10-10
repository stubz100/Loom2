---
updatedAt: 2026-06-29T14:06:22.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Pro Upscaler Precise

This guide shows how to upscale images using the Pro Upscaler Precise model via the Leonardo.AI REST API.

This guide shows how to upscale images using the Pro Upscaler Precise model via the Leonardo.AI REST API.

To learn about the benefits and best practices of this upscaler, please refer to <Anchor target="_blank" href="https://leonardo.ai/news/upscale-ai-generated-images/">this blog</Anchor>.

# Sample Request

```curl
curl --location 'https://cloud.leonardo.ai/api/rest/v2/generations' \
     --header 'authorization: Bearer {api-key}' \
     --header 'Content-Type: application/json' \
     --data '{
       "model": "aurora-upscaler-precise",
       "public": false,
       "parameters": {
         "height": 848,
         "width": 1264,
         "upscale_factor": 2,
         "upscale_mode": "clean",
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

<Recipe slug="use-pro-upscaler-precise-on-uploaded-image" title="Use Pro Upscaler Precise on Uploaded Image" />

<Recipe slug="use-pro-upscaler-creative-on-generated-and-variation-images" title="Use Pro Upscaler Creative on Generated and Variation Images" />

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

| Parameter                             | Type      | Definition                                                                                                                                              |
| :------------------------------------ | :-------- | :------------------------------------------------------------------------------------------------------------------------------------------------------ |
| height                                | `integer` | *Required.* Height of input image in pixels.                                                                                                            |
| model                                 | `string`  | *Required.* Set to `aurora-upscaler-precise`.                                                                                                           |
| parameters.upscale\_factor            | `integer` | *Required.* Controls Upscale Multiplier. Set to `2`, `3`, `4`, `5`, `6`, or `8`.                                                                        |
| parameters.upscale\_mode              | `string`  | *Required.* Controls Fix AI Image Artifacts toggle. Set to `clean`  to turn AI noise reduction on, or set to `detailed` to turn AI noise reduction off. |
| parameters.guidances.image\_reference | `array`   | *Required.* Array of 1 image to upscale. Each each image specifies an image.id and an image.type (`GENERATED` or `UPLOADED` or `VARIATION`).            |
| public                                | `boolean` | *Optional.* Set to `false` to keep result private.                                                                                                      |
| width                                 | `integer` | *Required.* Width of input image in pixels.                                                                                                             |

<br />