---
updatedAt: 2026-07-29T06:40:25.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# GPT Image 2

This guide shows how to generate images using GPT Image-2.0 model via the Leonardo.AI REST API.

This guide shows how to generate images using GPT Image-2.0 model via the Leonardo.AI REST API.

# Sample Request

```curl
curl --location 'https://cloud.leonardo.ai/api/rest/v2/generations' \
     --header 'authorization: Bearer {api-key}' \
     --header 'Content-Type: application/json' \
     --data '{
       "public": false,
       "model": "gpt-image-2",
       "parameters": {
           "quality": "MEDIUM",
           "prompt": "Koala with purple hat",
           "quantity": 2,
           "width": 1376,
           "height": 768,
           "prompt_enhance": "OFF",
           "guidances": {
               "image_reference": [
                   {
                       "image": {
                         "id": "00000000-0000-0000-0000-000000000001",
                         "type": "UPLOADED"
                       }
                   }
               ]
           }
        }
     }'
```

#

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

| Parameter                  | Type      | Definition                                                                                                                                                                               |
| :------------------------- | :-------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| guidances                  | `object`  | *Optional.* Object defining image guidance inputs that influence the generated result.                                                                                                   |
| guidances.image\_reference | `array`   | *Optional.* Array of up to 6 reference images. Each reference includes image.id, image.type (`GENERATED` or `UPLOADED`). Note: GPT Image 2 does not use `strength` for image references. |
| height                     | `integer` | *Optional.* Height input resolution.                                                                                                                                                     |
| model                      | `string`  | *Required.* Model identifier. Set to `gpt-image-2`.                                                                                                                                      |
| prompt                     | `string`  | *Required.* Text prompt describing what image you want the model to generate.                                                                                                            |
| prompt\_enhance            | `string`  | *Optional.* Enables prompt enhancement when set to `"ON"`; disabled when set to `"OFF"`.                                                                                                 |
| public                     | `boolean` | *Optional.* Boolean flag that determines whether the generation is public (`true`) or private (`false`).                                                                                 |
| quality                    | `string`  | *Optional.* Accepts `LOW`, `MEDIUM`, or `HIGH`.                                                                                                                                          |
| quantity                   | `integer` | *Optional.* Number of images to generate in a single request (1-8).                                                                                                                      |
| width                      | `integer` | *Optional.* Width input resolution.                                                                                                                                                      |

### Aspect Ratio Settings

| Aspect Ratio | Width | Height |
| :----------- | :---- | :----- |
| 1:1          | 1024  | 1024   |
| 2:3          | 848   | 1264   |
| 3:2          | 1264  | 848    |
| 16:9         | 1376  | 768    |
| 9:16         | 768   | 1376   |

#### Resolution Constraints

GPT Image 2 supports flexible custom resolutions with the following constraints:

* **Max edge length**<br />`max(width, height) < 3840`
* **Multiple of 16**<br />Both `width` and `height` must be **multiples of 16**.
* **Aspect ratio limit**<br />Let `long = max(width, height)` and `short = min(width, height)`.<br />`long / short ≤ 3`<br />(No aspect ratio wider than 3:1 or taller than 1:3.)
* **Pixel count range**<br />`655,360 ≤ width × height ≤ 8,294,400`
* **No auto sizing**<br />`size: "auto"` is **not supported** and must not be passed to the API.

<br />