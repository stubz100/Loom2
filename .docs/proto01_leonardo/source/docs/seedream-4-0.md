---
updatedAt: 2026-01-22T02:59:52.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Seedream 4.0

This guide shows how to generate images using Seedream 4.0 model via the Leonardo.AI REST API.

This guide shows how to generate images using Seedream 4.0 model via the Leonardo.AI REST API.

# Sample Request

```curl
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v2/generations \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '{
       "model": "seedream-4.0",
       "parameters": {
           "width": 1920,
           "height": 1080,
           "prompt": "Koala with purple wizard hat on a skateboard",
           "quantity": 2,
           "guidances": {
               "image_reference": [
                   {
                       "image": {
                           "id": "YOUR_UPLOADED_IMAGE_ID",
                           "type": "UPLOADED"
                       },
                       "strength": "MID"
                   }
               ]
           },
           "style_ids": [
               "111dc692-d470-4eec-b791-3475abac4c46"
           ]
       },
       "public": false
   }'
```

# Recipe

<Recipe slug="generate-with-seedream-40-model-using-uploaded-image" title="Generate with SeeDream 4.0 Model Using Uploaded Image" />

# API Request Endpoint, Headers, Parameters

## Endpoint

```curl
https://cloud.leonardo.ai/api/rest/v2/generations
```

### Headers

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
| model                      | `string`  | *Required.* Model identifier. Set to `seedream-4.0`.                                                                                                          |
| prompt                     | `string`  | *Required.* Text prompt describing what image you want the model to generate.                                                                                 |
| prompt\_enhance            | `string`  | *Optional.* Enables prompt enhancement when set to `"ON"`; disabled when set to `"OFF"`.                                                                      |
| public                     | `boolean` | *Optional.* Boolean flag that determines whether the generation is public (`true`) or private (`false`).                                                      |
| quantity                   | `integer` | *Optional.* Number of images to generate in a single request.                                                                                                 |
| seed                       | `integer` | *Optional.* Apply a fixed seed to maintain consistency across generation sets.                                                                                |
| style\_ids                 | `array`   | *Optional.* Array of style UUIDs used to apply preset artistic styles to the output.                                                                          |
| width                      | `integer` | *Optional.* Width input resolution. Supports `256` to `1440`.                                                                                                 |

### List of Style IDs

| Preset Style | UUID                                   |
| ------------ | -------------------------------------- |
| Cinematic    | `a5632c7c-ddbb-4e2f-ba34-8456ab3ac436` |
| Creative     | `6fedbf1f-4a17-45ec-84fb-92fe524a29ef` |
| Dynamic      | `111dc692-d470-4eec-b791-3475abac4c46` |
| Fashion      | `594c4a08-a522-4e0e-b7ff-e4dac4b6b622` |
| Portrait     | `ab5a4220-7c42-41e5-a578-eddb9fed3d75` |
| Stock Photo  | `5bdc3f2a-1be6-4d1c-8e77-992a30824a2c` |
| Vibrant      | `dee282d3-891f-4f73-ba02-7f8131e5541b` |

<br />