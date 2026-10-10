---
updatedAt: 2026-09-09T08:06:06.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# GPT Image 2.5 Flare

This guide shows how to generate images using the GPT Image 2.5 Flare model via the Leonardo.AI REST API.

# Sample Request

```curl
curl --location 'https://cloud.leonardo.ai/api/rest/v2/generations' \
     --header 'authorization: Bearer {api-key}' \
     --header 'Content-Type: application/json' \
     --data '{
       "public": false,
       "model": "openai/gpt-image-2.5-flare",
       "parameters": {
           "quality": "MEDIUM",
           "prompt": "Koala with purple hat",
           "quantity": 2,
           "width": 1376,
           "height": 768,
           "prompt_enhance": "OFF",
           "style_ids": [
               "111dc692-d470-4eec-b791-3475abac4c46"
           ],
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

| Parameter                  | Type      | Definition                                                                                                                                                                                                                                              |
| :------------------------- | :-------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| guidances                  | `object`  | *Optional.* Object defining image guidance inputs that influence the generated result.                                                                                                                                                                  |
| guidances.image\_reference | `array`   | *Optional.* Array of up to 16 reference images. Each reference includes image.id, image.type (`UPLOADED`, `GENERATED`, `VARIATION`, `URL`, or `BASE64`), and an optional order. Note: GPT Image 2.5 Flare does not use `strength` for image references. |
| height                     | `integer` | *Optional.* Height input resolution. Defaults to `1024`. Refer to the tables below for valid values.                                                                                                                                                    |
| model                      | `string`  | *Required.* Model identifier. Set to `openai/gpt-image-2.5-flare`.                                                                                                                                                                                      |
| prompt                     | `string`  | *Required.* Text prompt describing what image you want the model to generate. Maximum 9999 characters.                                                                                                                                                  |
| prompt\_enhance            | `string`  | *Optional.* Controls prompt enhancement. Accepts `AUTO`, `ON`, or `OFF`. Defaults to `AUTO`.                                                                                                                                                            |
| public                     | `boolean` | *Optional.* Boolean flag that determines whether the generation is public (`true`) or private (`false`).                                                                                                                                                |
| quality                    | `string`  | *Optional.* Accepts `LOW`, `MEDIUM`, `HIGH`, `XHIGH`, or `MAX`. Defaults to `MEDIUM`.                                                                                                                                                                   |
| quantity                   | `integer` | *Optional.* Number of images to generate in a single request (1-8). Defaults to `4`.                                                                                                                                                                    |
| style\_ids                 | `array`   | *Optional.* Array of style UUIDs used to apply preset artistic styles to the output (limited to 1 style). Defaults to `111dc692-d470-4eec-b791-3475abac4c46` (Dynamic). Refer to the table below.                                                       |
| width                      | `integer` | *Optional.* Width input resolution. Defaults to `1024`. Refer to the tables below for valid values.                                                                                                                                                     |

## List of Height and Width

| Model               | Height                                                                                                                                                                                                               | Width                                                                                                                                                                                          |
| :------------------ | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| GPT Image 2.5 Flare | 640, 672, 768, 832, 848, 864, 896, 928, 1024, 1136, 1152, 1184, 1200, 1248, 1264, 1280, 1344, 1376, 1536, 1584, 1632, 1648, 1696, 1792, 1824, 1856, 1920, 2016, 2048, 2336, 2448, 2560, 2880, 3200, 3264, 3504, 3584 | 768, 832, 848, 864, 896, 928, 1024, 1088, 1136, 1152, 1184, 1200, 1248, 1264, 1344, 1376, 1536, 1584, 1648, 1696, 1792, 1856, 2016, 2048, 2336, 2448, 2560, 2880, 3200, 3264, 3504, 3584, 3808 |

### Aspect Ratio Settings

| Aspect Ratio | Width | Height |
| :----------- | :---- | :----- |
| 1:1          | 1024  | 1024   |
| 2:3          | 848   | 1264   |
| 3:2          | 1264  | 848    |
| 16:9         | 1376  | 768    |
| 9:16         | 768   | 1376   |

#### Resolution Constraints

* **Discrete values only**<br />`width` and `height` must each be one of the values listed in the *List of Height and Width* table above.
* **No auto sizing**<br />`0` is not an accepted `width` or `height` value, and `size: "auto"` is not supported and must not be passed to the API.

## List of Style IDs

| Preset Style          | UUID                                   |
| :-------------------- | :------------------------------------- |
| 3D Render             | `debdf72a-91a4-467b-bf61-cc02bdeb69c6` |
| Acrylic               | `3cbb655a-7ca4-463f-b697-8a03ad67327c` |
| Cinematic             | `a5632c7c-ddbb-4e2f-ba34-8456ab3ac436` |
| Creative              | `6fedbf1f-4a17-45ec-84fb-92fe524a29ef` |
| Dynamic               | `111dc692-d470-4eec-b791-3475abac4c46` |
| Fashion               | `594c4a08-a522-4e0e-b7ff-e4dac4b6b622` |
| Game Concept          | `09d2b5b5-d7c5-4c02-905d-9f84051640f4` |
| Graphic Design 2D     | `703d6fe5-7f1c-4a9e-8da0-5331f214d5cf` |
| Graphic Design 3D     | `7d7c2bc5-4b12-4ac3-81a9-630057e9e89f` |
| Illustration          | `645e4195-f63d-4715-a3f2-3fb1e6eb8c70` |
| None                  | `556c1ee5-ec38-42e8-955a-1e82dad0ffa1` |
| Portrait              | `ab5a4220-7c42-41e5-a578-eddb9fed3d75` |
| Portrait Cinematic    | `4edb03c9-8a26-4041-9d01-f85b5d4abd71` |
| Portrait Fashion      | `0d34f8e1-46d4-428f-8ddd-4b11811fa7c9` |
| Pro B\&W photography  | `22a9a7d2-2166-4d86-80ff-22e2643adbcf` |
| Pro Color Photography | `7c3f932b-a572-47cb-9b9b-f20211e63b5b` |
| Pro Film Photography  | `581ba6d6-5aac-4492-bebe-54c424a0d46e` |
| Ray Traced            | `b504f83c-3326-4947-82e1-7fe9e839ec0f` |
| Stock Photo           | `5bdc3f2a-1be6-4d1c-8e77-992a30824a2c` |
| Vibrant               | `dee282d3-891f-4f73-ba02-7f8131e5541b` |
| Watercolor            | `1db308ce-c7ad-4d10-96fd-592fa6b75cc4` |