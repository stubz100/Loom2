---
updatedAt: 2026-01-22T05:27:17.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Nano Banana Pro

This guide shows how to generate images using Nano Banana Pro via the Leonardo.AI REST API.

This guide shows how to generate images using **Nano Banana Pro** via the Leonardo.AI REST API.

# Sample Request

```curl
curl --location 'https://cloud.leonardo.ai/api/rest/v2/generations' \
     --header 'authorization: Bearer {api-key}' \
     --header 'Content-Type: application/json' \
     --data '{
       "model": "gemini-image-2",
       "parameters": {
           "width": 1024,
           "height": 1024,
           "prompt": "a portrait-style photograph featuring a koala",
           "quantity": 1,
           "style_ids": [
                "111dc692-d470-4eec-b791-3475abac4c46"
           ],
           "prompt_enhance": "OFF"
        },
        "public": false
      }'
```

# Recipe

<Recipe slug="generate-with-nano-banana-pro-model-using-uploaded-image" title="Generate with Nano Banana Pro Model Using Uploaded Image" />

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

| Parameter                  | Type      | Definition                                                                                                                                                    |
| :------------------------- | :-------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| guidances                  | `object`  | *Optional.* Object defining image guidance inputs that influence the generated result.                                                                        |
| guidances.image\_reference | `array`   | *Optional.* Array of up to 6 reference images. Each reference includes image.id, image.type (`GENERATED` or `UPLOADED`), and strength (`LOW`, `MID`, `HIGH`). |
| height                     | `integer` | *Optional.* Height input resolution.                                                                                                                          |
| model                      | `string`  | *Required.* Model identifier. Refer to the table below for a list of models. Set to `gemini-image-2`.                                                         |
| prompt                     | `string`  | *Required.* Text prompt describing what image you want the model to generate.                                                                                 |
| prompt\_enhance            | `string`  | *Optional.* Enables prompt enhancement when set to `"ON"`; disabled when set to `"OFF"`.                                                                      |
| public                     | `boolean` | *Optional.* Boolean flag that determines whether the generation is public (`true`) or private (`false`).                                                      |
| quantity                   | `integer` | *Optional.* Number of images to generate in a single request. Default is 1, maximum is 8.                                                                     |
| seed                       | `integer` | *Optional.* Apply a fixed seed to maintain consistency across generation sets.                                                                                |
| style\_ids                 | `array`   | *Optional.* Array of style UUIDs used to apply preset artistic styles to the output.                                                                          |
| width                      | `integer` | *Optional.* Width input resolution.                                                                                                                           |

## List of Height and Width

| Model           | Height                                                                                                                                                                           | Width                                                                                                                                                                            |
| :-------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Nano Banana Pro | 0, 672, 768, 848, 896, 928, 1024, 1152, 1200, 1264, 1376, 1344, 1536, 1696, 1792, 1856, 2048, 2304, 2400, 2528, 2752, 2688, 3072, 3392, 3584, 3712, 4096, 4608, 4800, 5056, 5504 | 0, 672, 768, 848, 896, 928, 1024, 1152, 1200, 1264, 1376, 1344, 1536, 1696, 1792, 1856, 2048, 2304, 2400, 2528, 2752, 2688, 3072, 3392, 3584, 3712, 4096, 4608, 4800, 5056, 5504 |

When not specified, default height and width is 1024.

A width and height of 0 and 0 will allow the output to try to match the input image reference.

## List of Style IDs

| Preset Style          | UUID                                   |
| --------------------- | -------------------------------------- |
| 3D Render             | `debdf72a-91a4-467b-bf61-cc02bdeb69c6` |
| Acrylic               | `3cbb655a-7ca4-463f-b697-8a03ad67327c` |
| Creative              | `6fedbf1f-4a17-45ec-84fb-92fe524a29ef` |
| Dynamic               | `111dc692-d470-4eec-b791-3475abac4c46` |
| Fashion               | `594c4a08-a522-4e0e-b7ff-e4dac4b6b622` |
| Game Concept          | `09d2b5b5-d7c5-4c02-905d-9f84051640f4` |
| Graphic Design 2D     | `703d6fe5-7f1c-4a9e-8da0-5331f214d5cf` |
| Graphic Design 3D     | `7d7c2bc5-4b12-4ac3-81a9-630057e9e89f` |
| Illustration          | `645e4195-f63d-4715-a3f2-3fb1e6eb8c70` |
| None                  | `556c1ee5-ec38-42e8-955a-1e82dad0ffa1` |
| Portrait              | `8e2bc543-6ee2-45f9-bcd9-594b6ce84dcd` |
| Portrait Cinematic    | `4edb03c9-8a26-4041-9d01-f85b5d4abd71` |
| Portrait Fashion      | `0d34f8e1-46d4-428f-8ddd-4b11811fa7c9` |
| Pro B\&W photography  | `22a9a7d2-2166-4d86-80ff-22e2643adbcf` |
| Pro Color Photography | `7c3f932b-a572-47cb-9b9b-f20211e63b5b` |
| Pro Film Photography  | `581ba6d6-5aac-4492-bebe-54c424a0d46e` |
| Ray Traced            | `b504f83c-3326-4947-82e1-7fe9e839ec0f` |
| Stock Photo           | `5bdc3f2a-1be6-4d1c-8e77-992a30824a2c` |
| Watercolor            | `1db308ce-c7ad-4d10-96fd-592fa6b75cc4` |

# Image Guidance

## Sample Request

```curl
curl --location 'https://cloud.leonardo.ai/api/rest/v2/generations' \
     --header 'authorization: Bearer {api-key}' \
     --header 'Content-Type: application/json' \
     --data '{
       "model": "gemini-image-2",
       "parameters": {
           "width": 1024,
           "height": 1024,
           "prompt": "A koala is wearing a colourful Hawaiian shirt",
           "quantity": 1,
           "guidances": {
               "image_reference": [
                   {
                       "image": {
                           "id": "fc6f78c6-e7ac-491b-ad26-01f6843db870",
                           "type": "GENERATED"
                       },
                       "strength": "MID"
                   },
                   {
                       "image": {
                           "id": "a8e374dd-52f8-4236-ad9e-99b1f601fa3a",
                           "type": "UPLOADED"
                       },
                       "strength": "MID"
                   }
               ]
           },
           "style_ids": [
               "111dc692-d470-4eec-b791-3475abac4c46"
           ],
           "prompt_enhance": "OFF"
       },
       "public": false
   }'
```

## Recipe

<Recipe slug="generate-with-nano-banana-pro-model-using-uploaded-image" title="Generate with Nano Banana Pro Model Using Uploaded Image" />

<Recipe slug="uploading-an-image" title="Upload an Image and Print the Image ID" />

<br />